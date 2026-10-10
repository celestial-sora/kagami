"""Experimental Smart View sink: MiracleCast control + unprivileged RTP decode.

P2P/WFD interoperability still requires a real Galaxy and compatible Wi-Fi.
The desktop never stops NetworkManager or runs media processing as root.
"""

from collections import deque
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from .model import ReceiverError
from .pipeline import QUEUE, capture_format, gst, pipeline_error
from .transport import Device, command

HELPER = Path("/usr/local/libexec/kagami-smartview-helper")
MEDIA_PLUGINS = ("udpsrc", "rtpjitterbuffer", "rtpmp2tdepay", "tsdemux", "h264parse", "avdec_h264")


def interface_name(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,14}", value):
        raise ValueError("Choose an existing Wi-Fi interface, e.g. wlo1.")
    return value


def interface_modes(text):
    match = re.search(r"Supported interface modes:\s*\n((?:\s*\*[^\n]+\n)+)", text)
    return set(re.findall(r"\*\s+(\S+)", match[1])) if match else set()


def p2p_check(interface):
    interface = interface_name(interface)
    try:
        info = command(["iw", "dev", interface, "info"])
        match = re.search(r"\bwiphy\s+(\d+)", info)
        if not match:
            raise ValueError("Selected interface is not a wireless PHY.")
        modes = interface_modes(command(["iw", "phy", "phy" + match[1], "info"]))
        compatible = {"P2P-client", "P2P-GO"}.issubset(modes)
        return {"name": "wifi_direct", "ok": compatible,
                       "detail": "P2P client/GO advertised; Galaxy interoperability is unverified." if compatible else
                       "This Wi-Fi driver does not advertise P2P-client/P2P-GO. Smart View needs a compatible adapter/driver."}
    except (OSError, ValueError, RuntimeError) as exc:
        return {"name": "wifi_direct", "ok": False, "detail": str(exc)}


def preflight(interface):
    checks = [p2p_check(interface)]
    for binary in ("miracle-wifid", "miracle-sinkctl", "pkexec", "nmcli"):
        checks.append({"name": binary, "ok": bool(shutil.which(binary)), "detail": shutil.which(binary) or "Not installed"})
    installed = HELPER.is_file() and HELPER.stat().st_uid == 0 and not HELPER.stat().st_mode & 0o022
    checks.append({"name": "network_helper", "ok": installed, "detail": str(HELPER) if installed else "Install the root-owned helper using docs/smartview-ubuntu.md."})
    try:
        Gst = gst()
        missing = [name for name in MEDIA_PLUGINS if not Gst.ElementFactory.find(name)]
        checks.append({"name": "miracast_decoder", "ok": not missing, "detail": "H.264/RTP decoder ready" if not missing else "Missing: " + ", ".join(missing)})
    except RuntimeError as exc:
        checks.append({"name": "miracast_decoder", "ok": False, "detail": str(exc)})
    return checks


def media_description():
    # Matches MiracleCast's documented external player's MP2T/H.264 receive path.
    return ('udpsrc name=rtp port=7236 timeout=3000000000 caps="application/x-rtp,media=video,clock-rate=90000,encoding-name=MP2T" ! '
            'rtpjitterbuffer latency=100 drop-on-latency=true ! rtpmp2tdepay ! tsdemux ! '
            f'{QUEUE} ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=I420 ! ')


class SmartViewTransport:
    startup_timeout = None  # Wait for the user to select Kagami on the phone.

    def __init__(self, interface, *, allow_disconnect=False):
        self.interface = interface_name(interface)
        self.allow_disconnect = allow_disconnect
        self.identity = Device("smartview:" + interface, "listening", "Samsung Smart View", "miracast")
        self.state, self.process, self.pipeline, self.source = "stopped", None, None, None
        self.logs = deque(maxlen=20)
        self.reader = None
        self.last_frame = 0
        self.Gst = None

    def start(self, source, fps):
        failed = [item["detail"] for item in preflight(self.interface) if not item["ok"]]
        if failed:
            raise ReceiverError("unsupported", " ".join(failed))
        if not self.allow_disconnect:
            raise ReceiverError("permission", "Confirm that the selected Wi-Fi adapter may disconnect while Smart View is running; other adapters stay managed.")
        self.Gst, self.source = gst(), source
        self.pipeline = self.Gst.parse_launch(media_description() + "v4l2sink name=screen sync=false")
        screen = self.pipeline.get_by_name("screen")
        screen.set_property("device", source)
        screen.get_static_pad("sink").add_probe(self.Gst.PadProbeType.BUFFER, self._frame)
        if self.pipeline.set_state(self.Gst.State.PLAYING) == self.Gst.StateChangeReturn.FAILURE:
            raise ReceiverError("decoder", "Cannot start the Smart View video decoder.")
        # A fixed, installed helper handles only the selected adapter's P2P.
        # EOF on its control pipe restores network management even on app crash.
        self.process = subprocess.Popen(["pkexec", str(HELPER), self.interface], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        def read():
            for line in self.process.stdout:
                self.logs.append(line.strip())
        self.reader = threading.Thread(target=read, daemon=True, name="kagami-smartview-log")
        self.reader.start()
        self.state = "listening"

    def _frame(self, _pad, _info):
        self.last_frame = time.monotonic()
        return self.Gst.PadProbeReturn.OK

    def frame_format(self):
        return capture_format(self.source) if self.last_frame else None

    def failure(self):
        if self.process and self.process.poll() is not None:
            return ReceiverError("permission" if self.process.returncode == 126 else "connectivity",
                                 "Smart View network helper stopped. " + " ".join(list(self.logs))[-1000:])
        if self.pipeline:
            if error := pipeline_error(self.Gst, self.pipeline):
                return error
        if self.last_frame and time.monotonic() - self.last_frame > 4:
            return ReceiverError("connectivity", "Smart View stopped sending video. Disconnect on the phone, then restart the receiver.")
        return None

    def stop(self):
        if self.pipeline:
            self.pipeline.set_state(self.Gst.State.NULL)
            self.pipeline = None
        if self.process:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired as exc:
                raise ReceiverError("connectivity", "Network helper cleanup timed out; inspect it before reconnecting.") from exc
            if self.reader:
                self.reader.join(timeout=1)
            self.process.stdout.close()
            self.process = self.reader = None
        self.last_frame = 0
        self.state = "stopped"
