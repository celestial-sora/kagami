#!/usr/bin/env python3
"""Opt-in CI smoke: real UxPlay mDNS publication/teardown; no phone capture."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

binary = str(Path(sys.argv[1]).resolve())
name = "Kagami-QA-" + uuid.uuid4().hex[:8]
reservations = []
for candidate in range(36000, 37000, 3):
    try:
        for port in range(candidate, candidate + 3):
            for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                sock = socket.socket(socket.AF_INET, kind)
                reservations.append(sock)
                sock.bind(("0.0.0.0", port))
        break
    except OSError:
        for sock in reservations:
            sock.close()
        reservations.clear()
else:
    raise SystemExit("No free test ports")
for sock in reservations:
    sock.close()
with tempfile.TemporaryFile(mode="w+") as logs:
    process = subprocess.Popen([binary, "-rc", "/dev/null", "-n", name, "-nh", "-p", str(candidate),
                                "-m", "02:00:00:ca:fe:01", "-as", "fakesink", "-vrtp",
                                "pt=96 ! udpsink host=127.0.0.1 port=49999 sync=false"],
                               stdin=subprocess.DEVNULL, stdout=logs, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if process.poll() is not None:
                logs.seek(0)
                raise RuntimeError("UxPlay exited: " + logs.read()[-2000:])
            discovery = subprocess.run(["avahi-browse", "-pt", "_airplay._tcp"], capture_output=True, text=True, timeout=5)
            if name in discovery.stdout:
                break
            time.sleep(.2)
        else:
            raise RuntimeError("UxPlay AirPlay service was not advertised by Avahi")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            discovery = subprocess.run(["avahi-browse", "-pt", "_airplay._tcp"], capture_output=True, text=True, timeout=5)
            if name not in discovery.stdout:
                break
        else:
            raise RuntimeError("AirPlay test advertisement remained after UxPlay exit")
print("Real UxPlay AirPlay discovery and owned-process teardown passed; Apple protocol/media acceptance remains pending.")
