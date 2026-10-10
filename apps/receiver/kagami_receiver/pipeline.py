"""Shared raw-frame processing and persistent V4L2 output."""

import fcntl
import os
import struct
import threading
import time

from kagami_receiver.v4l2 import CAPABILITY, VIDIOC_QUERYCAP, query_device
from .model import FrameFormat, ReceiverError

QUEUE = "queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0"
REQUIRED = ("v4l2src", "v4l2sink", "videoconvert", "videocrop", "videoflip",
            "videoscale", "videobox", "videorate", "tee", "queue", "appsrc",
            "appsink", "input-selector", "videotestsrc")


def gst():
    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
    except (ImportError, ValueError) as exc:
        raise ReceiverError("decoder", "Install distribution PyGObject and GStreamer bindings.") from exc
    if Gst.version()[:2] < (1, 22):
        raise ReceiverError("unsupported", "GStreamer 1.22+ is required.")
    missing = [name for name in REQUIRED if not Gst.ElementFactory.find(name)]
    if missing:
        raise ReceiverError("decoder", "Missing GStreamer plugins: " + ", ".join(missing))
    return Gst


def capture_format(path):
    """Wait for exclusive_caps to advertise a producer and a negotiated size."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        capability = bytearray(CAPABILITY.size)
        fcntl.ioctl(fd, VIDIOC_QUERYCAP, capability, True)
        fields = CAPABILITY.unpack(capability)
        caps = fields[5] if fields[4] & 0x80000000 else fields[4]
        if not caps & 1:  # V4L2_CAP_VIDEO_CAPTURE; absent before writer attaches.
            return None
        data = bytearray(208)  # struct v4l2_format on 64-bit Fedora.
        struct.pack_into("I", data, 0, 1)  # V4L2_BUF_TYPE_VIDEO_CAPTURE
        fcntl.ioctl(fd, 0xC0D05604, data, True)  # VIDIOC_G_FMT
        width, height = struct.unpack_from("II", data, 8)
        if not (1 <= width <= 4096 and 1 <= height <= 4096):
            return None
        return FrameFormat(width, height)
    finally:
        os.close(fd)


def transform_description(frame, framing, output):
    x, y, w, h = framing.crop.pixels(frame.width, frame.height)
    elements = ["videoconvert", "video/x-raw,format=RGBA,pixel-aspect-ratio=1/1",
                f"videocrop left={x} top={y} right={frame.width-x-w} bottom={frame.height-y-h}"]
    rotations = {0: "none", 90: "clockwise", 180: "rotate-180", 270: "counterclockwise"}
    elements.append("videoflip method=" + rotations[framing.rotation])
    if framing.rotation in (90, 270):
        w, h = h, w
    if framing.mirror:
        elements.append("videoflip method=horizontal-flip")
    factor = (min if framing.fit == "fit" else max)(output.width / w, output.height / h)
    scaled_w, scaled_h = max(1, round(w * factor)), max(1, round(h * factor))
    elements += ["videoscale add-borders=false",
                 f"video/x-raw,width={scaled_w},height={scaled_h},pixel-aspect-ratio=1/1"]
    dx, dy = output.width - scaled_w, output.height - scaled_h
    if framing.fit == "fit":
        elements.append(f"videobox left={-(dx//2)} right={-(dx-dx//2)} top={-(dy//2)} bottom={-(dy-dy//2)} border-alpha=1")
    else:
        dx, dy = -dx, -dy
        elements.append(f"videocrop left={dx//2} right={dx-dx//2} top={dy//2} bottom={dy-dy//2}")
    elements += ["videorate name=rate", f"video/x-raw,format=RGBA,width={output.width},height={output.height},framerate={output.fps}/1,pixel-aspect-ratio=1/1"]
    return " ! ".join(elements)


def pipeline_error(Gst, pipeline):
    message = pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
    if message:
        if message.type == Gst.MessageType.EOS:
            return ReceiverError("connectivity", "Video source ended. Refresh devices and reconnect.")
        error, _debug = message.parse_error()
        return ReceiverError("decoder", str(error))
    return None


class CameraOutput:
    """Writer survives phone disconnects; black slate replaces missing frames."""
    def __init__(self, config, *, test_sink=None):
        self.config, self.test_sink = config, test_sink
        self.Gst = gst()
        self.pipeline = self.source = self.selector = None
        self.frames = 0

    def start(self):
        Gst, config = self.Gst, self.config
        if self.test_sink is None:
            query_device(config.device)
        caps = f"video/x-raw,format=RGBA,width={config.width},height={config.height},framerate={config.fps}/1,pixel-aspect-ratio=1/1"
        self.pipeline = Gst.parse_launch(
            "input-selector name=select sync-streams=true sync-mode=clock cache-buffers=false ! "
            f"{QUEUE} ! videoconvert ! video/x-raw,format=YUY2 ! " +
            (self.test_sink or "v4l2sink name=camera sync=false") + " " +
            f"videotestsrc is-live=true pattern=black ! {caps} ! select.sink_0 " +
            f"appsrc name=frames is-live=true format=time do-timestamp=true block=false max-buffers=2 leaky-type=downstream caps=\"{caps}\" ! select.sink_1")
        if self.test_sink is None:
            self.pipeline.get_by_name("camera").set_property("device", config.device)
        self.source = self.pipeline.get_by_name("frames")
        self.selector = self.pipeline.get_by_name("select")
        self.slate()
        self.selector.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self._count)
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise ReceiverError("format", "Cannot start the output; check permissions and device caps.")

    def _count(self, _pad, _info):
        self.frames += 1
        return self.Gst.PadProbeReturn.OK

    def push(self, sample):
        # Input and output have separate clocks. Timestamp at the writer boundary.
        buffer = sample.get_buffer().copy_deep()
        buffer.pts = buffer.dts = self.Gst.CLOCK_TIME_NONE
        buffer.duration = self.Gst.SECOND // self.config.fps
        result = self.source.emit("push-buffer", buffer)
        if result == self.Gst.FlowReturn.OK:
            self.selector.set_property("active-pad", self.selector.get_static_pad("sink_1"))
        return result

    def slate(self):
        if self.selector:
            self.selector.set_property("active-pad", self.selector.get_static_pad("sink_0"))

    def error(self):
        return pipeline_error(self.Gst, self.pipeline) if self.pipeline else None

    def stop(self):
        if self.pipeline:
            self.pipeline.set_state(self.Gst.State.NULL)
        self.pipeline = self.source = self.selector = None


class Processor:
    """Consume normalized transport frames; preview and output share transforms."""
    def __init__(self, frame, framing, config, output, *, test_source=None):
        self.frame, self.framing, self.config, self.output = frame, framing, config, output
        self.test_source, self.Gst = test_source, gst()
        self.pipeline = None
        self.lock = threading.Lock()
        self.preview = {}  # One latest frame per view; never queue images for GTK.
        self.received = self.processed = 0
        self.last_frame = 0
        self.pipeline_ms = None
        self.fault = None

    def start(self):
        Gst = self.Gst
        self.pipeline = Gst.parse_launch(
            (self.test_source or "v4l2src name=phone do-timestamp=true") + " ! " +
            f"video/x-raw,width={self.frame.width},height={self.frame.height} ! " +
            "videoconvert ! video/x-raw,format=RGBA,pixel-aspect-ratio=1/1 ! tee name=raw " +
            f"raw. ! {QUEUE} ! appsink name=screen emit-signals=true max-buffers=1 drop=true sync=false " +
            f"raw. ! {QUEUE} ! " + transform_description(self.frame, self.framing, self.config) +
            " ! appsink name=processed emit-signals=true max-buffers=1 drop=true sync=false")
        if self.test_source is None:
            self.pipeline.get_by_name("phone").set_property("device", self.config.source)
        for name in ("screen", "processed"):
            self.pipeline.get_by_name(name).connect("new-sample", self._sample, name)
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise ReceiverError("decoder", "Cannot read mirrored screen frames.")

    def _sample(self, sink, name):
        sample = sink.emit("pull-sample")
        if sample is None:
            return self.Gst.FlowReturn.EOS
        buffer = sample.get_buffer()
        now = time.monotonic()
        if name == "processed":
            result = self.output.push(sample)
            if result != self.Gst.FlowReturn.OK:
                self.fault = ReceiverError("format", "Output stopped accepting frames. Stop and restart the receiver.")
                return result
            self.processed += 1
            clock = self.pipeline.get_clock()
            if clock and buffer.pts != self.Gst.CLOCK_TIME_NONE:
                self.pipeline_ms = max(0, (clock.get_time() - self.pipeline.get_base_time() - buffer.pts) / self.Gst.MSECOND)
        else:
            self.received += 1
            self.last_frame = now
        structure = sample.get_caps().get_structure(0)
        width, height = structure.get_value("width"), structure.get_value("height")
        data = buffer.extract_dup(0, buffer.get_size())
        with self.lock:
            self.preview[name] = (width, height, data)
        return self.Gst.FlowReturn.OK

    def take_previews(self):
        with self.lock:
            result, self.preview = self.preview, {}
        return result

    def metrics(self):
        videorate = self.pipeline.get_by_name("rate") if self.pipeline else None
        # videorate reports actual rate adjustments; these are not transport drops.
        return {"frames_received": self.received, "frames_processed": self.processed,
                "rate_dropped": int(videorate.get_property("drop")) if videorate else 0,
                "rate_duplicated": int(videorate.get_property("duplicate")) if videorate else 0,
                "host_pipeline_ms": round(self.pipeline_ms, 1) if self.pipeline_ms is not None else None,
                "transport_dropped": None, "glass_to_glass_ms": None}

    def error(self):
        return self.fault or (pipeline_error(self.Gst, self.pipeline) if self.pipeline else None)

    def stop(self):
        # Do not hold the preview lock: set_state waits for streaming callbacks.
        if self.pipeline:
            self.pipeline.set_state(self.Gst.State.NULL)
        self.pipeline = None
        with self.lock:
            self.preview.clear()
