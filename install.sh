#!/usr/bin/env bash
# Fedora Workstation bootstrap. The application and build run as the caller.
set -euo pipefail

kagami_log() { printf '\nKagami · %s\n' "$*"; }
kagami_fail() { printf '\nKagami: %s\n' "$*" >&2; return 2; }

kagami_plan() {
    cat <<'PLAN'
Kagami installer · Fedora Workstation (DNF, systemd)
  1. Install GTK/Rust/GStreamer and system Python dependencies with sudo.
  2. Enable RPM Fusion Free if needed; install its v4l2loopback akmod.
  3. Build Kagami as your ordinary user, using the selected Git ref.
  4. Preserve existing settings/CA, or create local HTTPS configuration.
  5. Install an application-menu launcher and a narrow camera setup service.
  6. Allow HTTPS + bounded ICE UDP only from the selected local subnet.
Secure Boot may require password entry and one reboot to enroll a signing key.
Phone certificate trust and camera permission still need your first-time action.
--dry-run prints this plan without installing, downloading, or changing files.
PLAN
}

kagami_number() {
    local source=$1 config=$2 name number
    if [[ -f $config ]]; then
        PYTHONPATH="$source/apps/host" python3 - "$config" <<'PY'
from pathlib import Path
import sys
from kagami_host.config import load_config
print(int(load_config(Path(sys.argv[1])).device.removeprefix('/dev/video')))
PY
        return
    fi
    for name in /sys/class/video4linux/video*/name; do
        [[ -f $name ]] || continue
        if [[ $(cat "$name") == 'Kagami Virtual Camera' ]]; then
            number=${name%/name}; printf '%s\n' "${number##*/video}"; return
        fi
    done
    for ((number=10; number<=63; number++)); do
        if [[ ! -e /dev/video$number && ! -L /dev/video$number ]]; then
            printf '%s\n' "$number"; return
        fi
    done
    kagami_fail 'No free virtual camera slot between video10 and video63.'
}

kagami_main() {
    case ${1:-} in
        --help|--dry-run) kagami_plan; return 0 ;;
        '') ;;
        *) kagami_fail 'Supported options: --help, --dry-run'; return 2 ;;
    esac
    (( EUID != 0 )) || { kagami_fail 'Run this command as your desktop user, without sudo. The installer requests sudo only for system setup.'; return 2; }
    [[ $(uname -s) == Linux ]] || { kagami_fail 'This installer supports Fedora Workstation.'; return 2; }
    # os-release is a distribution-owned local shell data file.
    # shellcheck source=/dev/null
    . /etc/os-release
    [[ ${ID:-} == fedora && ! -e /run/ostree-booted ]] || {
        kagami_fail 'This installer requires DNF-based Fedora. Atomic/Silverblue and other distributions need separate packaging.'; return 2;
    }
    if command -v systemd-detect-virt >/dev/null && systemd-detect-virt --container --quiet; then
        kagami_fail 'Install on the Fedora desktop host, not inside a container.'; return 2
    fi
    command -v sudo >/dev/null || { kagami_fail 'sudo is required for system dependencies and the virtual camera.'; return 2; }
    local ref=${KAGAMI_REF:-main}
    [[ $ref =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && $ref != *..* ]] || { kagami_fail 'Invalid KAGAMI_REF.'; return 2; }
    local data=${XDG_DATA_HOME:-$HOME/.local/share} config=${XDG_CONFIG_HOME:-$HOME/.config}/kagami
    [[ $data == /* && $config == /* ]] || { kagami_fail 'XDG paths must be absolute.'; return 2; }
    local root=$data/kagami stage source kernel sha number network payload version pending=0
    mkdir -p "$root"
    exec 9> "$root/install.lock"
    flock -n 9 || { kagami_fail 'Another Kagami installation is already running.'; return 2; }
    KAGAMI_INSTALL_TEMP=$(mktemp -d "${TMPDIR:-/tmp}/kagami-install.XXXXXXXX")
    stage=$KAGAMI_INSTALL_TEMP
    # stage is always an installer-owned mktemp directory, never an input path.
    trap 'rm -rf -- "$KAGAMI_INSTALL_TEMP"' EXIT
    kagami_plan
    sudo -v
    kernel=$(uname -r)
    kagami_log 'Installing build and media dependencies'
    sudo dnf install -y git rust cargo gcc pkgconf-pkg-config gtk4-devel libadwaita-devel \
        python3 python3-gobject python3-aiohttp gstreamer1 gstreamer1-plugins-base \
        gstreamer1-plugins-good gstreamer1-plugins-bad-free libnice-gstreamer1 \
        openssl iproute v4l-utils akmods mokutil
    # Only this running kernel is requested; do not update/reboot it silently.
    sudo dnf install -y "kernel-devel-$kernel" || {
        kagami_fail "Development headers for $kernel are unavailable. Update/reboot Fedora to an installed supported kernel, then rerun this same command."; return 2;
    }
    if ! rpm -q rpmfusion-free-release >/dev/null 2>&1; then
        kagami_log 'Enabling RPM Fusion Free for the virtual camera driver'
        sudo dnf install -y "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm"
    fi
    # Keep an existing akmods key. Never replace it or disable Secure Boot.
    sudo kmodgenca -a
    sudo dnf install -y akmod-v4l2loopback v4l2loopback
    sudo akmods --force --kernels "$kernel" --akmod v4l2loopback
    if LC_ALL=C mokutil --sb-state 2>/dev/null | grep -q 'SecureBoot enabled'; then
        if ! sudo mokutil --test-key /etc/pki/akmods/certs/public_key.der >/dev/null 2>&1; then
            kagami_log 'Secure Boot needs the akmods signing key. Set an enrollment password now; after reboot choose Enroll MOK and enter that password.'
            if [[ -r /dev/tty ]]; then
                # The desktop user opens their own terminal; stdin is the curl pipe.
                # shellcheck disable=SC2024
                sudo mokutil --import /etc/pki/akmods/certs/public_key.der < /dev/tty
                pending=1
            else
                kagami_fail 'Run from an interactive terminal to enroll the Secure Boot key.'; return 2
            fi
        fi
    fi
    kagami_log "Downloading and building Kagami ($ref); first build may take several minutes"
    source=$stage/source
    git init -q "$source"
    git -C "$source" remote add origin https://github.com/celestial-sora/kagami.git
    git -C "$source" fetch --depth=1 origin "$ref"
    git -C "$source" checkout -q --detach FETCH_HEAD
    sha=$(git -C "$source" rev-parse HEAD)
    version=$root/versions/$sha-$(uname -m)
    # Cargo/build scripts run without sudo; no permanent root-running UI.
    if [[ ! -x $version/bin/kagami-linux ]]; then
        (cd "$source" && cargo build --release -p kagami-linux)
    fi
    number=$(kagami_number "$source" "$config/config.json")
    local host_args=()
    [[ -z ${KAGAMI_HOST:-} ]] || host_args=(--host "$KAGAMI_HOST")
    network=$stage/network.json
    python3 "$source/tools/install_config.py" --directory "$config" --device "/dev/video$number" "${host_args[@]}" > "$network"
    kagami_log 'Installing the desktop app and camera setup service'
    payload=$stage/payload
    mkdir -p "$payload/bin" "$root/versions"
    cp -a "$source/apps" "$source/tools" "$source/docs" "$source/README.md" "$source/LICENSE" "$payload/"
    if [[ -x $version/bin/kagami-linux ]]; then
        install -m 755 "$version/bin/kagami-linux" "$payload/bin/kagami-linux"
    else
        install -m 755 "$source/target/release/kagami-linux" "$payload/bin/kagami-linux"
    fi
    printf '%s\n' "$sha" > "$payload/VERSION"
    if [[ ! -d $version ]]; then mv "$payload" "$version"; fi
    python3 "$source/tools/install_launchers.py" --root "$root" --config "$config/config.json" --data "$data"
    sudo install -D -m 755 "$source/packaging/fedora/kagami-camera-setup" /usr/local/libexec/kagami-camera-setup
    sudo install -D -m 644 "$source/packaging/fedora/70-kagami-camera.rules" /etc/udev/rules.d/70-kagami-camera.rules
    cat > "$stage/kagami-camera.service" <<UNIT
[Unit]
Description=Kagami V4L2 virtual camera
Wants=akmods.service
After=akmods.service systemd-udevd.service systemd-modules-load.service
[Service]
Type=oneshot
ExecStart=/usr/local/libexec/kagami-camera-setup $number
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
    sudo install -m 644 "$stage/kagami-camera.service" /etc/systemd/system/kagami-camera.service
    sudo udevadm control --reload-rules
    sudo systemctl daemon-reload
    sudo systemctl enable kagami-camera.service
    if (( pending == 0 )); then
        sudo systemctl restart kagami-camera.service || {
            kagami_fail 'Virtual camera setup failed. Check Secure Boot/kernel compatibility with: journalctl -u kagami-camera.service'; return 2;
        }
        sudo udevadm trigger "/sys/class/video4linux/video$number"
        sudo udevadm settle
    fi
    if systemctl is-active --quiet firewalld; then
        local host subnet interface port udp_min udp_max zone rule protocol range
        read -r host subnet interface port udp_min udp_max < <(python3 - "$network" <<'PY'
import json, sys
n=json.load(open(sys.argv[1]))
print(n['host'], n['subnet'], n['interface'], n['port'], n['udp_min'], n['udp_max'])
PY
)
        zone=$(sudo firewall-cmd --get-zone-of-interface="$interface" || true)
        if [[ -z $zone || $zone == 'no zone' ]]; then zone=$(sudo firewall-cmd --get-default-zone); fi
        for protocol in tcp udp; do
            range=$port
            [[ $protocol == tcp ]] || range=$udp_min-$udp_max
            rule="rule family=\"ipv4\" source address=\"$subnet\" destination address=\"$host\" port port=\"$range\" protocol=\"$protocol\" accept"
            sudo firewall-cmd --zone="$zone" --permanent --add-rich-rule="$rule"
            sudo firewall-cmd --zone="$zone" --add-rich-rule="$rule"
        done
        cp "$network" "$config/installer-network.json"
    fi
    # Activate only a completed version. Previous versions/settings are retained.
    ln -s "$version" "$root/current.next.$$"
    mv -Tf "$root/current.next.$$" "$root/current"
    kagami_log "Installed $sha. Open Kagami from your application menu."
    printf 'Phone trust certificate: %s/tls/ca.pem\n' "$config"
    printf 'Transfer only ca.pem to your phone and complete its one-time certificate trust setup.\n'
    if (( pending )); then
        printf 'Camera setup pending: reboot, confirm Enroll MOK, then open Kagami.\n'
        return 10
    fi
    PYTHONPATH="$version/apps/host" python3 -m kagami_host doctor --config "$config/config.json" || {
        kagami_fail 'App installed, but diagnostics need attention. Review the report above before starting a stream.'; return 2;
    }
    kagami_log 'Linux setup checks passed. Phone/OBS hardware streaming still needs verification.'
}

# A pipe runs main; sourcing this file for installer tests only defines functions.
if [[ -z ${BASH_SOURCE[0]:-} || ${BASH_SOURCE[0]} == "$0" ]]; then kagami_main "$@"; fi
