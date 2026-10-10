#!/usr/bin/env bash
set -euo pipefail
device="${1:-/dev/video10}"
case "$device" in
  /dev/video[0-9]*) ;;
  *) echo "Supply /dev/videoN for a Kagami loopback device." >&2; exit 2 ;;
esac
# Reuse the actual V4L2 guard; never stream test frames into a physical camera.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$project_root/apps/receiver" "${KAGAMI_PYTHON:-python3}" -c \
  'import sys; from kagami_receiver.v4l2 import query_device; print(query_device(sys.argv[1]))' "$device"
exec gst-launch-1.0 -v videotestsrc is-live=true pattern=smpte \
  ! videoconvert ! video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1 \
  ! v4l2sink device="$device" sync=false
