#!/usr/bin/env bash
# Build pinned upstream as the caller, then stage files without root.
set -euo pipefail
source_dir=${1:?Source checkout directory required}
staging_dir=${2:?Empty staging directory required}
miracle_sha=0b7f1f1f6586dc65ff480f3cda5c2170a70aa020
[[ $source_dir == /* && $staging_dir == /* && ! -e $source_dir && ! -e $staging_dir ]] || {
    printf 'Use new absolute source and staging paths.\n' >&2; exit 2;
}
printf 'Kagami · Build MiracleCast: downloading pinned source\n'
git init -q "$source_dir"
git -C "$source_dir" remote add origin https://github.com/albfan/miraclecast.git
git -C "$source_dir" fetch --depth=1 origin "$miracle_sha" < /dev/null
git -C "$source_dir" checkout -q --detach FETCH_HEAD
[[ $(git -C "$source_dir" rev-parse HEAD) == "$miracle_sha" ]] || exit 2
printf 'Kagami · Build MiracleCast: configuring\n'
meson setup "$source_dir/build" "$source_dir" --prefix=/usr/local --sysconfdir=/etc \
    --buildtype=release -Denable-systemd=true -Dbuild-tests=false < /dev/null
printf 'Kagami · Build MiracleCast: compiling\n'
meson compile -C "$source_dir/build" < /dev/null
printf 'Kagami · Build MiracleCast: staging files\n'
DESTDIR="$staging_dir" meson install -C "$source_dir/build" --no-rebuild < /dev/null
# Dependencies retain upstream copyright/license and attribution.
for license in COPYING LICENSE_lgpl LICENSE_htable LICENSE_gdhcp; do
    install -D -m 644 "$source_dir/$license" "$staging_dir/usr/local/share/doc/kagami-miraclecast/$license"
done
printf '%s\n' "$miracle_sha" > "$staging_dir/usr/local/share/doc/kagami-miraclecast/VERSION"
