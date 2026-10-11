#!/usr/bin/env bash
# Compile only userspace tooling as the caller; stage pinned DKMS sources.
set -euo pipefail
source_dir=${1:?New absolute source directory required}
staging_dir=${2:?New absolute staging directory required}
loopback_sha=0f9ee86760b7f2bea174b7e3e7a1d38845da0ab4
[[ $source_dir == /* && $staging_dir == /* && ! -e $source_dir && ! -e $staging_dir ]] || exit 2
git init -q "$source_dir"
git -C "$source_dir" remote add origin https://github.com/umlaeute/v4l2loopback.git
git -C "$source_dir" fetch --depth=1 origin "$loopback_sha" < /dev/null
git -C "$source_dir" checkout -q --detach FETCH_HEAD
[[ $(git -C "$source_dir" rev-parse HEAD) == "$loopback_sha" ]] || exit 2
make -C "$source_dir/utils" < /dev/null
mkdir -p "$staging_dir/usr/src/v4l2loopback-0.15.4"
for item in Makefile Kbuild dkms.conf v4l2loopback.c v4l2loopback.h v4l2loopback_formats.h COPYING; do
    install -m 644 "$source_dir/$item" "$staging_dir/usr/src/v4l2loopback-0.15.4/$item"
done
install -D -m 755 "$source_dir/utils/v4l2loopback-ctl" "$staging_dir/usr/local/bin/v4l2loopback-ctl"
