#!/usr/bin/env python3
"""Compile lifecycle regressions against the actual built UxPlay callbacks."""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "gstreamer-app-1.0", "gstreamer-video-1.0",
     "gstreamer-sdp-1.0", "libplist-2.0", "openssl"], text=True))
libraries = [source / "build" / path for path in (
    "renderers/librenderers.a", "lib/libairplay.a", "lib/playfair/libplayfair.a", "lib/llhttp/libllhttp.a")]
with tempfile.TemporaryDirectory(prefix="kagami-lifecycle-qa-") as temporary:
    binary = str(Path(temporary) / "check")
    subprocess.run(["c++", "-std=gnu++11", "-O2", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    '-DUXPLAY_APPLICATION_SOURCE="' + str(source / "uxplay.cpp") + '"',
                    '-DUXPLAY_MIRROR_HEADER="' + str(source / "lib/raop_rtp_mirror.h") + '"',
                    '-DUXPLAY_NTP_HEADER="' + str(source / "lib/raop_ntp.h") + '"',
                    str(Path(__file__).with_suffix(".cpp")), *map(str, libraries),
                    "-o", binary, *flags, "-ldns_sd", "-pthread"], check=True)
    subprocess.run([binary], check=True, timeout=10)
