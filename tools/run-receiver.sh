#!/bin/sh
set -eu
kagami_receiver_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$kagami_receiver_root/apps/receiver${PYTHONPATH:+:$PYTHONPATH}"
exec "${KAGAMI_PYTHON:-python3}" -m kagami_receiver "$@"
