"""Connection lifecycle independent of UI and transport implementation."""

import fcntl
import os
from pathlib import Path
import time

from kagami_host.v4l2 import query_device
from .model import Framing, ReceiverError
from .pipeline import CameraOutput, Processor


class Receiver:
    def __init__(self, config):
        self.config = config
        self.state, self.error_message = "stopped", ""
        self.transport = self.output = self.processor = self.frame = None
        self.framing = Framing()
        self.locks = []
        self.started = 0
        self.last_metrics = (time.monotonic(), 0, 0)

    def _lock_devices(self):
        directory = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/kagami-{os.getuid()}"))
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        for node in sorted((self.config.source, self.config.device)):
            fd = os.open(directory / ("kagami-" + Path(node).name + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            self.locks.append(fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ReceiverError("permission", "Another Kagami receiver owns this loopback. Stop it first.") from exc

    def start(self, transport):
        if self.state not in ("stopped", "error", "disconnected"):
            raise ReceiverError("connectivity", "Stop the current connection first.")
        self.stop()
        self.error_message = ""
        self.transport = transport
        try:
            self._lock_devices()
            for node in (self.config.source, self.config.device):
                query_device(node)
            self.output = CameraOutput(self.config)
            self.output.start()
            transport.start(self.config.source, self.config.fps)
            self.started = time.monotonic()
            self.last_metrics = (self.started, 0, 0)
            self.state = "starting"
        except Exception:
            self.stop()
            raise

    def tick(self):
        if self.state not in ("starting", "live", "waiting"):
            return
        try:
            error = self.output.error() or self.transport.failure()
            if error:
                raise error
            if self.processor is None:
                self.frame = self.transport.frame_format()
                if self.frame:
                    self.processor = Processor(self.frame, self.framing, self.config, self.output)
                    self.processor.start()
                elif getattr(self.transport, "startup_timeout", 15) is not None and time.monotonic() - self.started > getattr(self.transport, "startup_timeout", 15):
                    raise ReceiverError("format", "scrcpy did not produce frames within 15 seconds. Check its V4L2 support and phone authorization.")
            if self.processor:
                if error := self.processor.error():
                    raise error
                if self.processor.last_frame:
                    self.transport.state = "live"
                    self.state = "live" if time.monotonic() - self.processor.last_frame < 3 else "waiting"
                    if self.state == "waiting":
                        self.output.slate()
                elif getattr(self.transport, "startup_timeout", 15) is not None and time.monotonic() - self.started > getattr(self.transport, "startup_timeout", 15):
                    raise ReceiverError("decoder", "No screen frames arrived. Check protected surfaces and scrcpy logs.")
        except (OSError, ValueError, RuntimeError) as exc:
            self.error_message = str(exc)
            if self.processor:
                self.processor.stop()
            self.processor = None
            self.output.slate()
            try:
                self.transport.stop()
            except RuntimeError as cleanup:
                self.error_message += " " + str(cleanup)
            # Leave the output writer/slate alive until Stop or explicit reconnect.
            self.state = "disconnected"

    def reframe(self, framing):
        self.framing = framing
        if self.processor:
            self.output.slate()
            self.processor.stop()
            self.processor = Processor(self.frame, framing, self.config, self.output)
            try:
                self.processor.start()
                self.started = time.monotonic()
                self.state = "starting"
            except Exception:
                self.processor.stop()
                self.processor = None
                raise

    def metrics(self):
        now = time.monotonic()
        previous, incoming, outgoing = self.last_metrics
        received = self.processor.received if self.processor else 0
        output = self.output.frames if self.output else 0
        elapsed = max(now - previous, .001)
        result = {"state": self.state, "device": self.config.device,
                  "incoming_fps": round(max(0, received - incoming) / elapsed, 1),
                  "output_fps": round(max(0, output - outgoing) / elapsed, 1),
                  "consumer_test": "manual verification pending"}
        if self.processor:
            result.update(self.processor.metrics())
        self.last_metrics = now, received, output
        return result

    def stop(self):
        errors = []
        for component in (self.processor, self.transport, self.output):
            if component:
                try:
                    component.stop()
                except (OSError, RuntimeError) as exc:
                    errors.append(exc)
        for fd in self.locks:
            os.close(fd)
        self.locks.clear()
        self.processor = self.transport = self.output = self.frame = None
        self.state = "stopped"
        if errors:
            raise errors[0]
