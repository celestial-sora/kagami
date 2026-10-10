#!/usr/bin/env bash
# Package the checked-out commit; never install or start receiver services.
set -euo pipefail
release_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$release_root"
release_version=$(cat VERSION)
[[ $release_version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { printf 'Invalid stable version\n' >&2; exit 2; }
release_output=${1:?Supply an output directory}
[[ $release_output == /* ]] || release_output="$release_root/$release_output"
git diff --quiet
git diff --cached --quiet
mkdir -p "$release_output"
release_tag="v$release_version"
git archive --format=tar --prefix="kagami-$release_tag/" HEAD | gzip -n > "$release_output/kagami-$release_tag-source.tar.gz"
python3 - "$release_tag" "$release_output/install-kagami.sh" <<'PY'
from pathlib import Path
import sys
source = Path('install.sh').read_text()
assert source.count('local ref=${KAGAMI_REF:-main}') == 1
source = source.replace('local ref=${KAGAMI_REF:-main}', 'local ref=${KAGAMI_REF:-' + sys.argv[1] + '}')
source = source.replace('default: main.', 'default: ' + sys.argv[1] + '.')
Path(sys.argv[2]).write_text(source)
Path(sys.argv[2]).chmod(0o755)
PY
bash -n "$release_output/install-kagami.sh"
printf '%s\n' "$(git rev-parse HEAD)" > "$release_output/COMMIT"
cp "docs/releases/$release_tag.md" "$release_output/RELEASE-NOTES.md"
(
    cd "$release_output"
    sha256sum "kagami-$release_tag-source.tar.gz" install-kagami.sh COMMIT RELEASE-NOTES.md > SHA256SUMS
    sha256sum --check SHA256SUMS
)
printf 'Packaged %s from %s\n' "$release_tag" "$(git rev-parse HEAD)"
