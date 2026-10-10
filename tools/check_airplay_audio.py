#!/usr/bin/env python3
"""Exercise the actual pinned audio renderer without a phone or host playback."""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "gstreamer-app-1.0"], text=True))
with tempfile.TemporaryDirectory(prefix="kagami-audio-qa-") as temporary:
    binary = str(Path(temporary) / "check")
    subprocess.run(["cc", "-O2", '-DUXPLAY_AUDIO_SOURCE="' + str(source / "renderers/audio_renderer.c") + '"',
                    str(Path(__file__).with_suffix(".c")), str(source / "lib/logger.c"),
                    "-o", binary, *flags, "-pthread"], check=True)
    subprocess.run([binary], check=True, timeout=15)
