#!/usr/bin/env bash
# Ubuntu V2 bootstrap. curl stdin never feeds package/build commands.
set -euo pipefail
kagami_log() { printf '\nKagami · %s\n' "$*"; }
kagami_fail() { printf '\nKagami: %s\n' "$*" >&2; return 2; }
kagami_plan() {
    cat <<'PLAN'
Kagami V2 installer · Ubuntu 24.04 / 26.04 desktop
  1. Check the requested commit against the active installed version.
  2. Download only if an update or --repair is needed.
  3. Install dependencies and matching camera/kernel prerequisites.
  4. Reuse verified pinned MiracleCast/UxPlay; build changed/missing backends.
  5. Install helpers, camera service and discovery.
  6. Check and activate the app; retain the previous version for rollback.
Run again to update. App/media never run as root.
Secure Boot enrollment may require a password/reboot; it is never disabled.
Smart View needs a P2P-capable adapter and Galaxy; hardware testing is pending.
AirPlay uses the same local network with iPhone/iPad/Mac; no P2P is needed.
Installation does not disconnect Wi-Fi or start a mirroring session.
--dry-run prints this plan without downloads, installation or file changes.
--repair repeats setup even at the same commit; verified backends are reused.
--rollback switches to the previous V2 app; --list-versions lists saved versions.
KAGAMI_REF accepts a branch, release tag or full commit; default: main.
PLAN
}
kagami_platform() {
    (( EUID != 0 )) || { kagami_fail 'Run as your desktop user, without sudo. System setup will request authentication.'; return 2; }
    [[ $(uname -s) == Linux ]] || { kagami_fail 'This installer supports Ubuntu desktops.'; return 2; }
    # shellcheck source=/dev/null
    . /etc/os-release
    [[ ${ID:-} == ubuntu && ( ${VERSION_ID:-} == 24.04 || ${VERSION_ID:-} == 26.04 ) ]] || {
        kagami_fail 'Use an Ubuntu 24.04 or 26.04 desktop. The former browser URL/QR bridge has been removed.'; return 2;
    }
    if command -v systemd-detect-virt >/dev/null && systemd-detect-virt --container --quiet; then
        kagami_fail 'Install on the desktop host, not in a container.'; return 2
    fi
    command -v sudo >/dev/null || { kagami_fail 'sudo is required for dependencies and the camera driver.'; return 2; }
    [[ -r /dev/tty && -w /dev/tty ]] || { kagami_fail 'Run the curl command in an interactive terminal for authentication.'; return 2; }
}
kagami_resolve_ref() {
    local ref=$1 refs
    if [[ $ref =~ ^[0-9a-f]{40}$ ]]; then printf '%s\n' "$ref"; return; fi
    refs=$(git ls-remote --exit-code https://github.com/celestial-sora/kagami.git \
        "refs/heads/$ref" "refs/tags/$ref" "refs/tags/$ref^{}" < /dev/null) || {
        kagami_fail "Cannot resolve $ref. Check the network and branch/release tag."; return 2;
    }
    # Prefer an annotated tag's commit over its tag object, then a branch.
    printf '%s\n' "$refs" | awk -v ref="$ref" '
        $2 == "refs/tags/" ref "^{}" { peeled=$1 }
        $2 == "refs/heads/" ref { branch=$1 }
        $2 == "refs/tags/" ref { tag=$1 }
        END { if (peeled) print peeled; else if (branch) print branch; else if (tag) print tag; else exit 2 }'
}
kagami_backend_stamp() {
    local hash
    hash=$(sha256sum "$1"); hash=${hash%% *}
    printf '%s:%s:%s:%s\n' "$hash" "$(uname -m)" "${ID:-unknown}" "${VERSION_ID:-unknown}"
}
kagami_backend_is_current() {
    local marker=$1 recipe=$2 binary
    shift 2
    [[ -f $marker && $(cat "$marker") == "$(kagami_backend_stamp "$recipe")" ]] || return 1
    for binary in "$@"; do
        [[ -x $binary ]] || return 1
        if [[ ${binary##*/} == kagami-uxplay ]]; then
            "$binary" -rc /dev/null -h > /dev/null 2>&1 || return 1
        else
            "$binary" --help > /dev/null 2>&1 || return 1
        fi
    done
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
    if [[ -f /etc/dbus-1/system.d/org.freedesktop.miracle.conf ]] &&
        kagami_backend_is_current /usr/local/share/doc/kagami-miraclecast/BUILD "$source/tools/build-miraclecast.sh" \
            /usr/local/bin/miracle-wifid /usr/local/bin/miracle-sinkctl /usr/local/bin/miracle-dhcp; then
        kagami_log '[4/6] Build: MiracleCast unchanged and usable; reusing installed binaries'
        return 0
    fi
    kagami_log '[4/6] Build: MiracleCast download, configure, compile and stage'
    bash "$source/tools/build-miraclecast.sh" "$stage/miraclecast" "$stage/miracle-payload" < /dev/null
    for binary in miracle-wifid miracle-sinkctl miracle-dhcp; do
        sudo install -D -o root -g root -m 755 "$stage/miracle-payload/usr/local/bin/$binary" "/usr/local/bin/$binary"
    done
    sudo install -D -o root -g root -m 644 "$stage/miracle-payload/etc/dbus-1/system.d/org.freedesktop.miracle.conf" /etc/dbus-1/system.d/org.freedesktop.miracle.conf
    for binary in COPYING LICENSE_lgpl LICENSE_htable LICENSE_gdhcp VERSION; do
        sudo install -D -o root -g root -m 644 "$stage/miracle-payload/usr/local/share/doc/kagami-miraclecast/$binary" "/usr/local/share/doc/kagami-miraclecast/$binary"
    done
    kagami_backend_stamp "$source/tools/build-miraclecast.sh" > "$stage/miracle-build-stamp"
    sudo install -o root -g root -m 644 "$stage/miracle-build-stamp" /usr/local/share/doc/kagami-miraclecast/BUILD
    sudo busctl --system call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig < /dev/null
    /usr/local/bin/miracle-wifid --help > /dev/null
    /usr/local/bin/miracle-sinkctl --help > /dev/null
}
kagami_install_dependencies() {
    local running=$1
    # shellcheck disable=SC2024
    sudo -v < /dev/tty
    kagami_log '[3/6] Install: Ubuntu dependencies and camera driver'
    sudo apt-get update < /dev/null
    # DKMS/shim-signed can ask for MOK enrollment via debconf on the terminal.
    # shellcheck disable=SC2024
    sudo apt-get install -y git build-essential meson ninja-build cmake pkg-config libglib2.0-dev \
        libreadline-dev libudev-dev libsystemd-dev python3 python3-gi python3-gi-cairo \
        libssl-dev libplist-dev libavahi-compat-libdnssd-dev libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev avahi-daemon \
        python3-cairo python3-gst-1.0 gir1.2-gtk-4.0 gstreamer1.0-tools \
        gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
        gstreamer1.0-libav iw network-manager wpasupplicant pkexec polkitd \
        iproute2 dbus v4l-utils v4l2loopback-dkms v4l2loopback-utils dkms mokutil \
        "linux-headers-$running" < /dev/tty
}
kagami_install_airplay() {
    local source=$1 stage=$2 item
    if kagami_backend_is_current /usr/local/share/doc/kagami-uxplay/BUILD "$source/tools/build-uxplay.sh" /usr/local/bin/kagami-uxplay &&
        /usr/local/bin/kagami-uxplay -rc /dev/null -h > /dev/null 2>&1; then
        kagami_log '[4/6] Build: UxPlay unchanged and usable; reusing installed binary'
        sudo systemctl enable --now avahi-daemon.service
        return 0
    fi
    kagami_log '[4/6] Build: UxPlay download, configure, compile and stage'
    bash "$source/tools/build-uxplay.sh" "$stage/uxplay" "$stage/uxplay-payload" < /dev/null
    # A dedicated binary preserves any independently installed UxPlay.
    sudo install -D -o root -g root -m 755 "$stage/uxplay-payload/usr/local/bin/uxplay" /usr/local/bin/kagami-uxplay
    for item in LICENSE LICENSE-llhttp VERSION; do
        sudo install -D -o root -g root -m 644 "$stage/uxplay-payload/usr/local/share/doc/kagami-uxplay/$item" "/usr/local/share/doc/kagami-uxplay/$item"
    done
    kagami_backend_stamp "$source/tools/build-uxplay.sh" > "$stage/uxplay-build-stamp"
    sudo install -o root -g root -m 644 "$stage/uxplay-build-stamp" /usr/local/share/doc/kagami-uxplay/BUILD
    sudo systemctl enable --now avahi-daemon.service
    /usr/local/bin/kagami-uxplay -rc /dev/null -h > /dev/null
}
kagami_main() {
    local repair=0 action=${1:-}
    case $action in
        --help|--dry-run) kagami_plan; return 0 ;;
        --repair) repair=1 ;;
        --rollback|--list-versions) ;;
        '') ;;
        *) kagami_fail 'Supported options: --help, --dry-run, --repair, --rollback, --list-versions'; return 2 ;;
    esac
    local ref=${KAGAMI_REF:-main}
    [[ $ref =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && $ref != *..* ]] || { kagami_fail 'Invalid KAGAMI_REF.'; return 2; }
    local data=${XDG_DATA_HOME:-$HOME/.local/share} config=${XDG_CONFIG_HOME:-$HOME/.config}/kagami
    [[ $data == /* && $config == /* ]] || { kagami_fail 'XDG paths must be absolute.'; return 2; }
    local root=$data/kagami source sha version stage running output input interface status helper
    local pending=0 interface_args=() kagami_settings=()
    mkdir -p "$root"
    exec 9> "$root/install.lock"
    flock -n 9 || { kagami_fail 'Another Kagami installation is running.'; return 2; }
    if [[ $action == --rollback || $action == --list-versions ]]; then
        [[ -f $root/manage_versions.py ]] || { kagami_fail 'Install this V2 updater before using rollback/version commands.'; return 2; }
        if [[ $action == --rollback ]]; then action=rollback; else action=versions; fi
        python3 "$root/manage_versions.py" --root "$root" "$action"
        return
    fi
    kagami_platform
    kagami_log "[1/6] Check: resolving $ref and reading the installed commit"
    # An existing installation already has git. Fresh machines bootstrap it here.
    if ! command -v git >/dev/null; then
        kagami_log '[1/6] Check: installing git for version resolution'
        # shellcheck disable=SC2024
        sudo -v < /dev/tty
        sudo apt-get update < /dev/null
        sudo apt-get install -y git < /dev/null
    fi
    sha=$(kagami_resolve_ref "$ref")
    [[ $sha =~ ^[0-9a-f]{40}$ ]] || { kagami_fail 'Remote ref did not resolve to a commit.'; return 2; }
    version=$root/versions/v2-$sha-$(uname -m)
    if (( repair == 0 )) && [[ -L $root/current && $(readlink -f "$root/current") == "$version" &&
        -f $version/VERSION && $(cat "$version/VERSION") == "$sha" && -f $version/tools/run-receiver.sh ]]; then
        kagami_log "Already installed at $sha. No download, package installation or backend build needed."
        if [[ -n ${KAGAMI_INTERFACE:-} ]]; then
            python3 "$version/tools/install_receiver.py" prepare --config "$config/receiver-install.json" --interface "$KAGAMI_INTERFACE"
            python3 "$version/tools/install_receiver.py" launchers --root "$root" --config "$config/receiver-install.json" --data "$data"
        fi
        printf 'Use --repair for camera/kernel prerequisites or an incomplete installation.\n'
        return 0
    fi
    KAGAMI_INSTALL_TEMP=$(mktemp -d "${TMPDIR:-/tmp}/kagami-install.XXXXXXXX")
    stage=$KAGAMI_INSTALL_TEMP
    trap 'rm -rf -- "$KAGAMI_INSTALL_TEMP"' EXIT
    kagami_plan
    kagami_log "[2/6] Download: Kagami $ref → $sha"
    source=$stage/source
    git init -q "$source"
    git -C "$source" remote add origin https://github.com/celestial-sora/kagami.git
    git -C "$source" fetch --depth=1 origin "$sha" < /dev/null
    git -C "$source" checkout -q --detach FETCH_HEAD
    [[ $(git -C "$source" rev-parse HEAD) == "$sha" ]] || { kagami_fail 'Downloaded commit differs from the checked version.'; return 2; }
    running=$(uname -r)
    kagami_install_dependencies "$running"
    kagami_camera_module "$running"
    if kagami_secure_boot; then :; else
        status=$?
        (( status == 10 )) || return "$status"
        pending=1
    fi
    kagami_install_miraclecast "$source" "$stage"
    kagami_install_airplay "$source" "$stage"
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
    kagami_log '[5/6] Install: helpers, camera boot service and app payload'
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
        PYTHONPATH="$source/apps/receiver" python3 - "/dev/video$output" "/dev/video$input" <<'PY'
import sys
from kagami_receiver.v4l2 import query_device
for device in sys.argv[1:]:
    query_device(device)
PY
    fi
    kagami_log '[6/6] Verify: software and camera prerequisites before app activation'
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
    # Keep previous app versions/settings and presets; replace the entry point.
    cp "$source/tools/manage_versions.py" "$root/manage_versions.next.py"
    mv -f "$root/manage_versions.next.py" "$root/manage_versions.py"
    python3 "$source/tools/install_receiver.py" launchers --root "$root" --config "$config/receiver-install.json" --data "$data"
    python3 "$root/manage_versions.py" --root "$root" activate "$version"
    kagami_log "Installed Kagami V2 $sha. Open Kagami from your application menu."
    printf 'Smart View adapter: %s. Camera output: /dev/video%s. Screen input: /dev/video%s.\n' "$interface" "$output" "$input"
    printf 'CLI: %s/.local/bin/kagami smartview-doctor\n' "$HOME"
    printf 'Saved versions: kagami versions. Previous app: kagami rollback (restart the app after switching).\n'
    printf 'Samsung Smart View is experimental; real Galaxy/OBS verification remains pending.\n'
    printf 'AirPlay is experimental; select AirPlay, then Screen Mirroring → Kagami on iPhone/iPad/Mac. No URL/QR connection is used.\n'
    if (( pending )); then
        printf 'Installation complete; prerequisites pending (exit 10). Complete MOK enrollment/reboot if requested, or use a P2P-capable Wi-Fi adapter.\n'
        return 10
    fi
    kagami_log 'Software/camera checks passed. In Kagami confirm the selected adapter may disconnect, then Start; on Galaxy select Smart View → Kagami.'
}
# A pipe runs main; sourcing this script for tests only defines functions.
if [[ -z ${BASH_SOURCE[0]:-} || ${BASH_SOURCE[0]} == "$0" ]]; then kagami_main "$@"; fi
