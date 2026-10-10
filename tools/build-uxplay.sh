#!/usr/bin/env bash
# Build the inspected UxPlay backend as the caller, stage without root.
set -euo pipefail
source_dir=${1:?Source checkout directory required}
staging_dir=${2:?Empty staging directory required}
uxplay_sha=4764e4619e8924f43601d778277fc9f0bf280597
[[ $source_dir == /* && $staging_dir == /* && ! -e $source_dir && ! -e $staging_dir ]] || {
    printf 'Use new absolute source and staging paths.\n' >&2; exit 2;
}
printf 'Kagami · Build UxPlay: downloading pinned source\n'
git init -q "$source_dir"
git -C "$source_dir" remote add origin https://github.com/FDH2/UxPlay.git
git -C "$source_dir" fetch --depth=1 origin "$uxplay_sha" < /dev/null
git -C "$source_dir" checkout -q --detach FETCH_HEAD
[[ $(git -C "$source_dir" rev-parse HEAD) == "$uxplay_sha" ]] || exit 2
# v1.73.2 uses printf here without declaring it; GCC 14+ rejects this.
# Keep the pinned source and compiler diagnostics, adding the missing header.
python3 - "$source_dir/renderers/video_renderer.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
source = path.read_text()
anchor = '#include "video_renderer.h"\n'
if source.count(anchor) != 1:
    raise SystemExit("Pinned UxPlay header context changed; review the compatibility fix.")
path.write_text(source.replace(anchor, '#include <stdio.h>\n' + anchor, 1))
PY
printf 'Kagami · Build UxPlay: configuring\n'
cmake -S "$source_dir" -B "$source_dir/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local -DNO_MARCH_NATIVE=ON -DNO_X11_DEPS=ON < /dev/null
printf 'Kagami · Build UxPlay: compiling\n'
cmake --build "$source_dir/build" --parallel 2 < /dev/null
printf 'Kagami · Build UxPlay: staging files\n'
DESTDIR="$staging_dir" cmake --install "$source_dir/build" < /dev/null
install -D -m 644 "$source_dir/LICENSE" "$staging_dir/usr/local/share/doc/kagami-uxplay/LICENSE"
install -D -m 644 "$source_dir/lib/llhttp/LICENSE-MIT" "$staging_dir/usr/local/share/doc/kagami-uxplay/LICENSE-llhttp"
printf '%s\n' "$uxplay_sha" > "$staging_dir/usr/local/share/doc/kagami-uxplay/VERSION"
