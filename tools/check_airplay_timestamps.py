#!/usr/bin/env python3
"""Compile a regression check against the real downloaded UxPlay source."""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "gstreamer-app-1.0", "gstreamer-video-1.0"], text=True))
with tempfile.TemporaryDirectory(prefix="kagami-rtp-qa-") as temporary:
    binary = str(Path(temporary) / "check")
    subprocess.run(["cc", "-O2", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    '-DUXPLAY_VIDEO_SOURCE="' + str(source / "renderers/video_renderer.c") + '"',
                    str(Path(__file__).with_suffix(".c")), str(source / "lib/logger.c"),
                    "-o", binary, *flags, "-pthread"], check=True)
    subprocess.run([binary], check=True, timeout=30)
