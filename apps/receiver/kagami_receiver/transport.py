"""ADB/scrcpy adapter using the documented V4L2 sink, never server internals."""

from collections import deque
from dataclasses import dataclass
import ipaddress
import os
import re
import signal
import subprocess
import threading
from typing import Protocol

from .model import ReceiverError


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    model: str
    connection: str


class Transport(Protocol):
    identity: Device
    state: str

    def start(self, source: str, fps: int): ...
    def stop(self): ...
    def failure(self): ...
    def frame_format(self): ...


def command(args, *, input=None, timeout=10):
    try:
        result = subprocess.run(args, input=input, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise ReceiverError("unsupported", f"Install {args[0]} on the Linux host.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReceiverError("connectivity", f"{args[0]} timed out; check the connection.") from exc
    if result.returncode:
        raise ReceiverError("connectivity", (result.stderr or result.stdout).strip()[:1000])
    return result.stdout


def parse_devices(text):
    devices = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] == "List" or fields[0].startswith("*"):
            continue
        attributes = dict(item.split(":", 1) for item in fields[2:] if ":" in item)
        network = ":" in fields[0] or "_adb-tls-connect._tcp" in fields[0]
        # Positive USB identification; do not accidentally classify mDNS as USB.
        connection = "wifi" if network else "usb" if "usb" in attributes else "unknown"
        devices.append(Device(fields[0], fields[1], attributes.get("model", fields[0]).replace("_", " "), connection))
    return devices


def devices():
    return parse_devices(command(["adb", "devices", "-l"]))


def endpoint(value):
    # Wireless debugging uses an explicit private IP and port from Android's UI.
    match = re.fullmatch(r"(\[[0-9a-fA-F:]+\]|[0-9.]+):([0-9]{1,5})", value)
    if not match:
        raise ValueError("Use the IP:port shown in Android Wireless debugging.")
    address = ipaddress.ip_address(match[1].strip("[]"))
    if not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError("Use a reachable private network address.")
    if not 1 <= int(match[2]) <= 65535:
        raise ValueError("Invalid network port.")
    return value


def pair(address, code):
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("Enter the six-digit Android pairing code.")
    # Keep the code out of argv and stored settings/logs.
    result = command(["adb", "pair", endpoint(address)], input=code + "\n", timeout=30)
    if "Successfully paired" not in result:
        raise ReceiverError("permission", "Pairing failed; use a fresh code from Android.")
    return "Android pairing completed. Connect using its debugging IP:port."


def connect(address):
    result = command(["adb", "connect", endpoint(address)])
    if "connected to" not in result.lower():
        raise ReceiverError("connectivity", "Cannot connect; check the debugging IP:port and local network.")
    return result.strip()


def scrcpy_capabilities():
    version = command(["scrcpy", "--version"])
    help_text = command(["scrcpy", "--help"])
    match = re.search(r"scrcpy\s+(\d+)\.(\d+)", version)
    required = ("--v4l2-sink", "--no-video-playback", "--no-audio", "--no-control",
                "--capture-orientation", "--max-size", "--max-fps")
    missing = [flag for flag in required if flag not in help_text]
    if not match or int(match[1]) < 3 or missing:
        raise ReceiverError("unsupported", "Install Linux scrcpy 3.0+ with V4L2 support. Missing flags: " + ", ".join(missing))
    return version.splitlines()[0]


class ScrcpyTransport:
    def __init__(self, identity, mode="usb"):
        if mode not in ("usb", "wifi"):
            raise ReceiverError("unsupported", "Smart View is unverified; Google Cast is research-only.")
        self.identity, self.mode = identity, mode
        self.state, self.process, self.reader = "stopped", None, None
        self.logs = deque(maxlen=20)
        self.version = None
        self.source = None

    def start(self, source, fps):
        if self.process:
            raise ReceiverError("connectivity", "This transport is already running.")
        current = next((item for item in devices() if item.serial == self.identity.serial), None)
        if current is None or current.state != "device":
            raise ReceiverError("permission" if current and current.state == "unauthorized" else "connectivity",
                                "Unlock the phone and authorize USB debugging, then refresh devices.")
        if current.connection != self.mode:
            raise ReceiverError("connectivity", "Select a device that matches the connection mode; Kagami never switches networks automatically.")
        self.version = scrcpy_capabilities()
        self.source = source
        args = ["scrcpy", f"--serial={current.serial}", f"--v4l2-sink={source}",
                "--no-video-playback", "--no-audio", "--no-control",
                "--capture-orientation=@", "--max-size=1920", f"--max-fps={fps}"]
        try:
            self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
        except OSError as exc:
            raise ReceiverError("connectivity", f"Cannot start scrcpy: {exc}") from exc
        self.logs.clear()
        self.state = "starting"
        def read():
            for line in self.process.stdout:
                self.logs.append(line.strip())
        self.reader = threading.Thread(target=read, daemon=True, name="kagami-scrcpy-log")
        self.reader.start()

    def failure(self):
        if self.process and self.process.poll() is not None:
            self.state = "error"
            return ReceiverError("connectivity", "Screen mirroring stopped. Check USB/ADB authorization. " + " ".join(list(self.logs))[-1000:])
        return None

    def frame_format(self):
        from .pipeline import capture_format
        return capture_format(self.source) if self.source else None

    def stop(self):
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
        self.state = "stopped"
