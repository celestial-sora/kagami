#!/usr/bin/env bash
# Ubuntu V2 bootstrap. curl stdin never feeds package/build commands.
set -euo pipefail
kagami_log() { printf '\nKagami · %s\n' "$*"; }
kagami_fail() { printf '\nKagami: %s\n' "$*" >&2; return 2; }
kagami_plan() {
    cat <<'PLAN'
Kagami V2 installer · Ubuntu 24.04 / 26.04 desktop
  1. Install GTK4/GStreamer, Wi-Fi Direct tools and matching kernel headers.
  2. Build pinned MiracleCast as your ordinary user.
  3. Install root-owned helpers and two guarded virtual camera nodes.
  4. Replace the Kagami launcher with the new native screen receiver.
  5. Preserve settings/presets and report Smart View prerequisites.
Run again to update. App/media never run as root.
Secure Boot enrollment may require a password/reboot; it is never disabled.
Smart View needs a P2P-capable adapter and Galaxy; hardware testing is pending.
Installation does not disconnect Wi-Fi or start a mirroring session.
--dry-run prints this plan without downloads, installation or file changes.
PLAN
}
kagami_platform() {
    (( EUID != 0 )) || { kagami_fail 'Run as your desktop user, without sudo. System setup will request authentication.'; return 2; }
    [[ $(uname -s) == Linux ]] || { kagami_fail 'This installer supports Ubuntu desktops.'; return 2; }
    # shellcheck source=/dev/null
    . /etc/os-release
    [[ ${ID:-} == ubuntu && ( ${VERSION_ID:-} == 24.04 || ${VERSION_ID:-} == 26.04 ) ]] || {
        kagami_fail 'Use an Ubuntu 24.04 or 26.04 desktop. Historical Fedora V1 setup is install-v1.sh.'; return 2;
    }
    if command -v systemd-detect-virt >/dev/null && systemd-detect-virt --container --quiet; then
        kagami_fail 'Install on the desktop host, not in a container.'; return 2
    fi
    command -v sudo >/dev/null || { kagami_fail 'sudo is required for dependencies and the camera driver.'; return 2; }
    [[ -r /dev/tty && -w /dev/tty ]] || { kagami_fail 'Run the curl command in an interactive terminal for authentication.'; return 2; }
}
kagami_camera_module() {
    local running=$1 vermagic
    sudo dkms autoinstall -k "$running" < /dev/null || { kagami_fail "DKMS camera build failed for $running. Review the log above."; return 2; }
    vermagic=$(modinfo -k "$running" -F vermagic v4l2loopback) || { kagami_fail "No camera module for $running; matching headers are required."; return 2; }
    [[ $vermagic == "$running "* ]] || { kagami_fail "Camera module does not match $running."; return 2; }
}
kagami_secure_boot() {
    local certificate
    if ! LC_ALL=C mokutil --sb-state 2>/dev/null | grep -q 'SecureBoot enabled'; then return 0; fi
    for certificate in /var/lib/shim-signed/mok/MOK.der /var/lib/dkms/mok.pub; do
        if sudo test -f "$certificate"; then
            if sudo mokutil --test-key "$certificate" >/dev/null 2>&1; then return 0; fi
            kagami_log 'Secure Boot: set an enrollment password; on reboot choose Enroll MOK and confirm it.'
            # stdin is the curl pipe; enrollment reads the user's terminal.
            # shellcheck disable=SC2024
            sudo mokutil --import "$certificate" < /dev/tty || return 2
            return 10
        fi
    done
    kagami_fail 'Secure Boot is enabled but no DKMS signing certificate was found. Configure Ubuntu DKMS signing, then rerun.'
}
kagami_install_miraclecast() {
    local source=$1 stage=$2 binary
    bash "$source/tools/build-miraclecast.sh" "$stage/miraclecast" "$stage/miracle-payload" < /dev/null
    for binary in miracle-wifid miracle-sinkctl miracle-dhcp; do
        sudo install -D -o root -g root -m 755 "$stage/miracle-payload/usr/local/bin/$binary" "/usr/local/bin/$binary"
    done
    sudo install -D -o root -g root -m 644 "$stage/miracle-payload/etc/dbus-1/system.d/org.freedesktop.miracle.conf" /etc/dbus-1/system.d/org.freedesktop.miracle.conf
    for binary in COPYING LICENSE_lgpl LICENSE_htable LICENSE_gdhcp VERSION; do
        sudo install -D -o root -g root -m 644 "$stage/miracle-payload/usr/local/share/doc/kagami-miraclecast/$binary" "/usr/local/share/doc/kagami-miraclecast/$binary"
    done
    sudo busctl --system call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig < /dev/null
    /usr/local/bin/miracle-wifid --help > /dev/null
    /usr/local/bin/miracle-sinkctl --help > /dev/null
}
kagami_install_dependencies() {
    local running=$1
    # shellcheck disable=SC2024
    sudo -v < /dev/tty
    kagami_log 'Installing Ubuntu dependencies and camera driver'
    sudo apt-get update < /dev/null
    # DKMS/shim-signed can ask for MOK enrollment via debconf on the terminal.
    # shellcheck disable=SC2024
    sudo apt-get install -y git build-essential meson ninja-build pkg-config libglib2.0-dev \
        libreadline-dev libudev-dev libsystemd-dev python3 python3-gi python3-gi-cairo \
        python3-cairo python3-gst-1.0 gir1.2-gtk-4.0 gstreamer1.0-tools \
        gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
        gstreamer1.0-libav iw network-manager wpasupplicant pkexec polkitd \
        iproute2 dbus v4l-utils v4l2loopback-dkms v4l2loopback-utils dkms mokutil \
        "linux-headers-$running" < /dev/tty
}
kagami_main() {
    case ${1:-} in
        --help|--dry-run) kagami_plan; return 0 ;;
        '') ;;
        *) kagami_fail 'Supported options: --help, --dry-run'; return 2 ;;
    esac
    kagami_platform
    local ref=${KAGAMI_REF:-main}
    [[ $ref =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && $ref != *..* ]] || { kagami_fail 'Invalid KAGAMI_REF.'; return 2; }
    local data=${XDG_DATA_HOME:-$HOME/.local/share} config=${XDG_CONFIG_HOME:-$HOME/.config}/kagami
    [[ $data == /* && $config == /* ]] || { kagami_fail 'XDG paths must be absolute.'; return 2; }
    local root=$data/kagami source sha version stage running output input interface status helper
    local pending=0 interface_args=() kagami_settings=()
    mkdir -p "$root"
    exec 9> "$root/install.lock"
    flock -n 9 || { kagami_fail 'Another Kagami installation is running.'; return 2; }
    KAGAMI_INSTALL_TEMP=$(mktemp -d "${TMPDIR:-/tmp}/kagami-install.XXXXXXXX")
    stage=$KAGAMI_INSTALL_TEMP
    trap 'rm -rf -- "$KAGAMI_INSTALL_TEMP"' EXIT
    kagami_plan
    running=$(uname -r)
    kagami_install_dependencies "$running"
    kagami_camera_module "$running"
    if kagami_secure_boot; then :; else
        status=$?
        (( status == 10 )) || return "$status"
        pending=1
    fi
    kagami_log "Downloading Kagami ($ref)"
    source=$stage/source
    git init -q "$source"
    git -C "$source" remote add origin https://github.com/celestial-sora/kagami.git
    git -C "$source" fetch --depth=1 origin "$ref" < /dev/null
    git -C "$source" checkout -q --detach FETCH_HEAD
    sha=$(git -C "$source" rev-parse HEAD)
    version=$root/versions/v2-$sha-$(uname -m)
    kagami_log 'Building the pinned MiracleCast receiver (no root build)'
    kagami_install_miraclecast "$source" "$stage"
    [[ -z ${KAGAMI_INTERFACE:-} ]] || interface_args=(--interface "$KAGAMI_INTERFACE")
    python3 "$source/tools/install_receiver.py" prepare --config "$config/receiver-install.json" "${interface_args[@]}" > "$stage/settings.json"
    mapfile -t kagami_settings < <(python3 - "$stage/settings.json" <<'PY'
import json, sys
settings = json.load(open(sys.argv[1]))
for key in ('output', 'source', 'interface'):
    print(settings[key].removeprefix('/dev/video'))
PY
)
    (( ${#kagami_settings[@]} == 3 )) || { kagami_fail 'Cannot read receiver settings.'; return 2; }
    output=${kagami_settings[0]}; input=${kagami_settings[1]}; interface=${kagami_settings[2]}
    kagami_log 'Installing root-owned helpers and boot camera service'
    for helper in kagami-camera-setup kagami-receiver-camera-setup; do
        sudo install -D -o root -g root -m 755 "$source/packaging/fedora/$helper" "/usr/local/libexec/$helper"
    done
    for helper in kagami-smartview-helper kagami-smartview-session; do
        sudo install -D -o root -g root -m 755 "$source/packaging/ubuntu/$helper" "/usr/local/libexec/$helper"
    done
    sudo install -D -o root -g root -m 644 "$source/packaging/fedora/70-kagami-camera.rules" /etc/udev/rules.d/70-kagami-camera.rules
    cat > "$stage/kagami-receiver-camera.service" <<UNIT
[Unit]
Description=Kagami receiver camera nodes
After=systemd-udevd.service systemd-modules-load.service
[Service]
Type=oneshot
ExecStart=/usr/local/libexec/kagami-receiver-camera-setup $output $input
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
    sudo install -o root -g root -m 644 "$stage/kagami-receiver-camera.service" /etc/systemd/system/kagami-receiver-camera.service
    sudo udevadm control --reload-rules
    sudo systemctl daemon-reload
    sudo systemctl enable kagami-receiver-camera.service
    if (( pending == 0 )); then
        sudo systemctl restart kagami-receiver-camera.service || {
            kagami_fail 'Camera setup failed. Check journalctl -u kagami-receiver-camera.service. Existing cameras were not unloaded.'; return 2;
        }
        sudo udevadm trigger --subsystem-match=video4linux
        sudo udevadm settle
        PYTHONPATH="$source/apps/host" python3 - "/dev/video$output" "/dev/video$input" <<'PY'
import sys
from kagami_host.v4l2 import query_device
for device in sys.argv[1:]:
    query_device(device)
PY
    fi
    if python3 "$source/tools/install_receiver.py" check --config "$config/receiver-install.json"; then status=0; else status=$?; fi
    (( status == 0 || status == 10 )) || { kagami_fail 'Receiver software checks failed; previous app remains active.'; return 2; }
    (( status != 10 )) || pending=1
    mkdir -p "$root/versions"
    if [[ ! -d $version ]]; then
        mkdir "$stage/app-payload"
        cp -a "$source/apps" "$source/tools" "$source/docs" "$source/README.md" "$source/LICENSE" "$stage/app-payload/"
        printf '%s\n' "$sha" > "$stage/app-payload/VERSION"
        mv "$stage/app-payload" "$version"
    fi
    # Keep previous app versions/config/CA and presets; replace the entry point.
    ln -s "$version" "$root/current.next.$$"
    mv -Tf "$root/current.next.$$" "$root/current"
    python3 "$source/tools/install_receiver.py" launchers --root "$root" --config "$config/receiver-install.json" --data "$data"
    kagami_log "Installed Kagami V2 $sha. Open Kagami from your application menu."
    printf 'Smart View adapter: %s. Camera output: /dev/video%s. Screen input: /dev/video%s.\n' "$interface" "$output" "$input"
    printf 'CLI: %s/.local/bin/kagami smartview-doctor\n' "$HOME"
    printf 'Samsung Smart View is experimental; real Galaxy/OBS verification remains pending.\n'
    if (( pending )); then
        printf 'Installation complete; prerequisites pending (exit 10). Complete MOK enrollment/reboot if requested, or use a P2P-capable Wi-Fi adapter.\n'
        return 10
    fi
    kagami_log 'Software/camera checks passed. In Kagami confirm the selected adapter may disconnect, then Start; on Galaxy select Smart View → Kagami.'
}
# A pipe runs main; sourcing this script for tests only defines functions.
if [[ -z ${BASH_SOURCE[0]:-} || ${BASH_SOURCE[0]} == "$0" ]]; then kagami_main "$@"; fi
