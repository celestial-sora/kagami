"""AirPlay screen receiver using an owned UxPlay process and local RTP bridge.

UxPlay handles discovery/protocol. This module decodes H.264 into a fixed,
letterboxed screen loopback; the shared processor performs the user's crop.
"""
from collections import deque
import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time

from .model import ReceiverError
from .pipeline import QUEUE, capture_format, gst, pipeline_error
from .transport import Device, command
from .v4l2 import set_output_fps

MEDIA_PLUGINS = ("udpsrc", "rtph264depay", "h264parse", "avdec_h264")


def capabilities():
    binary = shutil.which("kagami-uxplay") or shutil.which("uxplay")
    if not binary:
        raise ReceiverError("unsupported", "Install Kagami's AirPlay backend by rerunning the curl installer.")
    help_text = command([binary, "-rc", "/dev/null", "-h"])
    match = re.search(r"UxPlay\s+(\d+)\.(\d+)(?:\.(\d+))?", help_text)
    if not match or tuple(map(int, match.groups()[:2])) < (1, 73) or any(
            flag not in help_text for flag in ("-vrtp", "-rc", "-as", "-nh", "-p")):
        raise ReceiverError("unsupported", "UxPlay 1.73+ with -vrtp/-rc is required; rerun the Kagami installer.")
    return {"binary": binary, "version": match[0]}


def preflight():
    checks = []
    try:
        info = capabilities()
        checks.append({"name": "airplay_backend", "ok": True, "detail": info["version"]})
    except (OSError, ValueError, RuntimeError) as exc:
        checks.append({"name": "airplay_backend", "ok": False, "detail": str(exc)})
    try:
        result = subprocess.run(["systemctl", "is-active", "avahi-daemon.service"],
                                capture_output=True, text=True, timeout=5)
        active = result.returncode == 0 and result.stdout.strip() == "active"
        checks.append({"name": "airplay_discovery", "ok": active,
                       "detail": "Avahi active; use the same local network" if active else
                       "Avahi is inactive; rerun the curl installer or start avahi-daemon."})
    except (OSError, subprocess.SubprocessError) as exc:
        checks.append({"name": "airplay_discovery", "ok": False, "detail": str(exc)})
    try:
        Gst = gst()
        missing = [name for name in MEDIA_PLUGINS if not Gst.ElementFactory.find(name)]
        checks.append({"name": "airplay_decoder", "ok": not missing,
                       "detail": "H.264/RTP decoder ready" if not missing else "Missing: " + ", ".join(missing)})
    except RuntimeError as exc:
        checks.append({"name": "airplay_decoder", "ok": False, "detail": str(exc)})
    return checks


def media_description(fps):
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("Use 1–60 FPS.")
    return ('udpsrc name=rtp address=127.0.0.1 timeout=3000000000 '
            'caps="application/x-rtp,media=video,clock-rate=90000,encoding-name=H264,payload=96" ! '
            'rtph264depay ! '
            f'h264parse ! avdec_h264 ! {QUEUE} ! videoconvert ! videoscale add-borders=true ! videorate skip-to-first=true ! '
            f'video/x-raw,format=I420,width=1280,height=720,pixel-aspect-ratio=1/1,framerate={fps}/1 ! ')


class AirPlayTransport:
    startup_timeout = None  # Wait until a user selects Screen Mirroring → Kagami.

    def __init__(self, port=35000):
        if type(port) is not int or not 1024 <= port <= 65533:
            raise ValueError("AirPlay port must leave room for three ports between 1024 and 65535.")
        self.port = port
        self.identity = Device("airplay", "listening", "AirPlay", "airplay")
        self.state, self.process, self.reader = "stopped", None, None
        self.pipeline = self.source = self.Gst = None
        self.logs = deque(maxlen=20)
        self.last_frame = 0

    def start(self, source, fps):
        if self.process or self.pipeline:
            raise ReceiverError("connectivity", "Stop the current AirPlay session first.")
        failed = [c["detail"] for c in preflight() if not c["ok"]]
        if failed:
            raise ReceiverError("unsupported", " ".join(failed))
        self.Gst, self.source = gst(), source
        try:
            set_output_fps(source, fps)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            self.pipeline = self.Gst.parse_launch(media_description(fps) + "v4l2sink name=screen sync=false")
            self.pipeline.get_by_name("rtp").set_property("port", port)
            screen = self.pipeline.get_by_name("screen")
            screen.set_property("device", source)
            screen.get_static_pad("sink").add_probe(self.Gst.PadProbeType.BUFFER, self._frame)
            if self.pipeline.set_state(self.Gst.State.PLAYING) == self.Gst.StateChangeReturn.FAILURE:
                raise ReceiverError("decoder", "Cannot start the AirPlay video decoder.")
            # The bridge is loopback-only. Ignore personal UxPlay startup options,
            # which could otherwise enable recordings or redirect this pipeline.
            args = [capabilities()["binary"], "-rc", "/dev/null", "-n", "Kagami", "-nh",
                    "-s", f"1280x720@{fps}", "-p", str(self.port), "-as", "0", "-vrtp",
                    f"pt=96 config-interval=1 ! udpsink host=127.0.0.1 port={port} sync=false"]
            self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
            self.logs.clear()
            process = self.process
            def read():
                for line in process.stdout:
                    self.logs.append(line.strip())
            self.reader = threading.Thread(target=read, daemon=True, name="kagami-airplay-log")
            self.reader.start()
            self.state = "listening"
        except Exception:
            self.stop()
            raise

    def _frame(self, _pad, _info):
        self.last_frame = time.monotonic()
        return self.Gst.PadProbeReturn.OK

    def frame_format(self):
        return capture_format(self.source) if self.last_frame else None

    def failure(self):
        if self.process and self.process.poll() is not None:
            return ReceiverError("connectivity", "AirPlay backend stopped. " + " ".join(self.logs)[-1000:])
        if self.pipeline:
            if error := pipeline_error(self.Gst, self.pipeline):
                return error
        if self.last_frame and time.monotonic() - self.last_frame > 4:
            return ReceiverError("connectivity", "AirPlay stopped sending video. Stop mirroring on the device, then restart Kagami reception.")
        return None

    def stop(self):
        # Stop decoding immediately, then reap the owned discovery/protocol group.
        if self.pipeline:
            self.pipeline.set_state(self.Gst.State.NULL)
            self.pipeline = None
        process = self.process
        if process:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=3)
            if self.reader:
                self.reader.join(timeout=1)
            process.stdout.close()
        self.process = self.reader = None
        self.last_frame = 0
        self.state = "stopped"
