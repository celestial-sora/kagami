#!/usr/bin/env bash
# Build/package as the caller, never install system prerequisites or run root.
set -euo pipefail
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:?Supply a new absolute build directory}
[[ $output == /* && ! -e $output && $EUID != 0 ]] || { printf 'Use a new absolute build directory as your normal user.\n' >&2; exit 2; }
[[ $(uname -m) == x86_64 ]] || { printf 'Initial AppImage target: x86_64.\n' >&2; exit 2; }
for command in patchelf mksquashfs curl python3; do command -v "$command" > /dev/null; done
mkdir -p "$output"
# Versioned upstream assets + checked digests; never use mutable continuous.
curl -fL --retry 3 https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage -o "$output/appimagetool.AppImage"
curl -fL --retry 3 https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64 -o "$output/runtime-x86_64"
printf '%s  %s\n' ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0 "$output/appimagetool.AppImage" \
    2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d "$output/runtime-x86_64" | sha256sum --check
chmod +x "$output/appimagetool.AppImage"
# Extract tool locally: building requires no FUSE mount or root.
(cd "$output"; ./appimagetool.AppImage --appimage-extract > /dev/null)
bash "$root/tools/build-uxplay.sh" "$output/uxplay-source" "$output/uxplay-stage"
/usr/bin/python3 "$root/tools/build-appdir.py" "$output/Kagami.AppDir" "$output/uxplay-stage/usr/local/bin/uxplay"
cp "$output/uxplay-stage/usr/local/share/doc/kagami-uxplay/"* "$output/Kagami.AppDir/usr/share/doc/kagami/"
G_DEBUG=fatal-criticals "$output/Kagami.AppDir/AppRun" --appimage-check
ARCH=x86_64 "$output/squashfs-root/AppRun" --runtime-file "$output/runtime-x86_64" \
    "$output/Kagami.AppDir" "$output/Kagami-$(cat "$root/VERSION")-x86_64.AppImage"
(cd "$output"; sha256sum Kagami-*-x86_64.AppImage > SHA256SUMS)
printf 'AppImage built in %s; host camera driver, discovery and Smart View helper are separate prerequisites.\n' "$output"
