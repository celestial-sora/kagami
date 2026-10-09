"""Phase 0 GStreamer receiver. This requires real Linux GStreamer/GI and V4L2.

The output pipeline stays alive between phone sessions. A live no-signal source
feeds the same V4L2 writer whenever the phone disconnects or stops producing.
"""

import asyncio
import threading
import time

from .v4l2 import query_device

REQUIRED_PLUGINS = ("webrtcbin", "nicesrc", "nicesink", "rtpvp8depay", "vp8dec",
                    "videoconvert", "videoscale", "videorate", "videotestsrc",
                    "textoverlay", "input-selector", "queue", "v4l2sink")


def gst_modules():
    try:
        import gi
        gi.require_version("Gst", "1.0")
        gi.require_version("GstWebRTC", "1.0")
        gi.require_version("GstSdp", "1.0")
        from gi.repository import GLib, Gst, GstSdp, GstWebRTC
    except (ImportError, ValueError) as exc:
        raise RuntimeError("GStreamer/PyGObject is unavailable in this Python interpreter. See docs/fedora-setup.md.") from exc
    Gst.init(None)
    missing = [name for name in REQUIRED_PLUGINS if not Gst.ElementFactory.find(name)]
    if missing:
        raise RuntimeError("Missing GStreamer plugins: " + ", ".join(missing))
    if Gst.version()[:2] < (1, 22):
        raise RuntimeError("Kagami's reference receiver requires GStreamer 1.22 or newer.")
    return GLib, Gst, GstSdp, GstWebRTC


def configure_ice_ports(receiver, minimum, maximum):
    ice = receiver.get_property("ice-agent")
    # webrtcbin constructs a floating ICE object. Some GI versions consume
    # its sole reference while wrapping this property, leaving two owners
    # with one reference. Restore webrtcbin's ownership only in that case.
    # An already-sunk/fixed binding reports both references and needs no fix.
    if ice.__grefcount__ == 1:
        ice._ref()
    ice.set_property("min-rtp-port", minimum)
    ice.set_property("max-rtp-port", maximum)
    return ice


class GstReceiver:
    def __init__(self, config, emit):
        self.config, self.emit = config, emit
        self.GLib, self.Gst, self.Sdp, self.WebRTC = gst_modules()
        self.loop = asyncio.get_running_loop()
        self.mainloop = self.GLib.MainLoop()
        self.thread = threading.Thread(target=self.mainloop.run, name="kagami-gstreamer", daemon=True)
        self.thread.start()
        self.lock = threading.RLock()
        self.pipeline = self.selector = self.slate = self.webrtc = self.branch = self.video_pad = None
        self.generation = 0
        self.remote_ready = False
        self.pending_ice = []
        self.last_frame = 0.0
        self.received = self.output_frames = 0
        self.sample = (time.monotonic(), 0, 0)
        self.fault = None
        self.watchdog_id = None

    async def _run(self, function):
        future = self.loop.create_future()

        def complete(value=None, error=None):
            if not future.done():
                if error:
                    future.set_exception(error)
                else:
                    future.set_result(value)

        def invoke():
            try:
                value = function()
                self.loop.call_soon_threadsafe(complete, value)
            except Exception as exc:
                self.loop.call_soon_threadsafe(complete, None, exc)
            return self.GLib.SOURCE_REMOVE

        self.GLib.idle_add(invoke)
        return await asyncio.wait_for(future, timeout=10)

    def _publish(self, message, generation=None):
        def deliver():
            if generation is None or generation == self.generation:
                self.emit({"v": 1, **message})
        self.loop.call_soon_threadsafe(deliver)

    def _error(self, message, generation=None):
        self._publish({"type": "error", "message": str(message)}, generation)

    async def start(self):
        await self._run(self._start)

    def _start(self):
        Gst = self.Gst
        query_device(self.config.device)
        caps = (f"video/x-raw,format=I420,width={self.config.width},"
                f"height={self.config.height},framerate={self.config.fps}/1")
        self.pipeline = Gst.parse_launch(
            "input-selector name=selector sync-streams=true sync-mode=clock "
            "cache-buffers=true drop-backwards=true ! "
            "queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! "
            "videoconvert ! video/x-raw,format=YUY2 ! v4l2sink name=output sync=false "
            f"videotestsrc is-live=true pattern=black ! {caps} ! "
            'textoverlay text="Kagami: no signal" halignment=center valignment=center '
            'font-desc="Sans 24" ! selector.sink_0'
        )
        self.selector = self.pipeline.get_by_name("selector")
        self.slate = self.selector.get_static_pad("sink_0")
        self.selector.set_property("active-pad", self.slate)
        output = self.pipeline.get_by_name("output")
        output.set_property("device", self.config.device)
        output.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, self._count_output)
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._bus_message)
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Cannot start the virtual camera output.")
        result, _, _ = self.pipeline.get_state(5 * Gst.SECOND)
        if result not in (Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.NO_PREROLL):
            raise RuntimeError("Virtual camera did not become ready. Check device permissions and caps.")
        self.watchdog_id = self.GLib.timeout_add(500, self._watchdog)

    def _count_output(self, _pad, _info):
        self.output_frames += 1
        return self.Gst.PadProbeReturn.OK

    def _watchdog(self):
        if self.last_frame and time.monotonic() - self.last_frame > 3:
            self.selector.set_property("active-pad", self.slate)
        return self.GLib.SOURCE_CONTINUE

    def _bus_message(self, _bus, message):
        if message.type == self.Gst.MessageType.ERROR:
            error, _debug = message.parse_error()
            self.fault = str(error)
            self._error(self.fault)

    async def begin_session(self):
        await self._run(self._begin_session)

    def _begin_session(self):
        if self.fault:
            raise RuntimeError("Output pipeline has failed; stop and restart the host.")
        self._stop_stream()
        Gst = self.Gst
        self.webrtc = Gst.ElementFactory.make("webrtcbin", "phone-receiver")
        self.webrtc.set_property("bundle-policy", self.WebRTC.WebRTCBundlePolicy.MAX_BUNDLE)
        self.webrtc.set_property("latency", 60)
        configure_ice_ports(self.webrtc, self.config.udp_port_min, self.config.udp_port_max)
        # No STUN/TURN server is configured. All media stays on the local link.
        self.webrtc.connect("on-ice-candidate", self._on_ice, self.generation)
        self.webrtc.connect("pad-added", self._on_pad, self.generation)
        self.pipeline.add(self.webrtc)
        if not self.webrtc.sync_state_with_parent():
            raise RuntimeError("Cannot start WebRTC receiver; inspect GStreamer/libnice installation.")

    def _on_ice(self, _webrtc, index, candidate, generation):
        self._publish({"type": "ice", "candidate": {"candidate": candidate,
                      "sdpMLineIndex": index}}, generation)

    def _on_pad(self, _webrtc, pad, generation):
        Gst = self.Gst
        if pad.direction != Gst.PadDirection.SRC:
            return
        with self.lock:
            if generation != self.generation or self.branch is not None:
                return
            caps = pad.get_current_caps() or pad.query_caps(None)
            structure = caps.get_structure(0)
            encoding = structure.get_string("encoding-name")
            if encoding and encoding.upper() != "VP8":
                self._error("Phase 0 requires VP8 video; reload the supplied client.", generation)
                return
            try:
                description = (
                    "queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! "
                    "rtpvp8depay ! vp8dec ! videoconvert ! videoscale ! videorate ! "
                    f"video/x-raw,format=I420,width={self.config.width},height={self.config.height},"
                    f"framerate={self.config.fps}/1 ! "
                    "queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0"
                )
                self.branch = Gst.parse_bin_from_description(description, True)
                self.pipeline.add(self.branch)
                self.video_pad = self.selector.request_pad_simple("sink_%u")
                if self.branch.get_static_pad("src").link(self.video_pad) != Gst.PadLinkReturn.OK:
                    raise RuntimeError("Cannot connect decoded frames to output selector.")
                self.branch.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self._count_video, generation)
                if not self.branch.sync_state_with_parent():
                    raise RuntimeError("Cannot start video decoder.")
                if pad.link(self.branch.get_static_pad("sink")) != Gst.PadLinkReturn.OK:
                    raise RuntimeError("Cannot connect WebRTC RTP to VP8 decoder.")
            except Exception as exc:
                self._error(str(exc), generation)

    def _count_video(self, _pad, _info, generation):
        with self.lock:
            if generation == self.generation:
                self.received += 1
                self.last_frame = time.monotonic()
                self.selector.set_property("active-pad", self.video_pad)
        return self.Gst.PadProbeReturn.OK

    async def offer(self, sdp):
        await self._run(lambda: self._offer(sdp))

    def _offer(self, text):
        Gst, generation, receiver = self.Gst, self.generation, self.webrtc
        result, message = self.Sdp.SDPMessage.new()
        if result != self.Sdp.SDPResult.OK or self.Sdp.sdp_message_parse_buffer(text.encode(), message) != self.Sdp.SDPResult.OK:
            raise ValueError("GStreamer could not parse the SDP offer.")
        description = self.WebRTC.WebRTCSessionDescription.new(self.WebRTC.WebRTCSDPType.OFFER, message)

        def reply_ok(promise):
            if generation != self.generation:
                return False
            if promise.wait() != Gst.PromiseResult.REPLIED:
                self._error("WebRTC negotiation did not complete.", generation)
                return False
            reply = promise.get_reply()
            if reply and reply.has_field("error"):
                self._error(str(reply.get_value("error")), generation)
                return False
            return True

        def local_set(promise, *_):
            if reply_ok(promise):
                self._publish({"type": "answer", "sdp": answer_text[0]}, generation)

        answer_text = []

        def answer_created(promise, *_):
            if not reply_ok(promise):
                return
            reply = promise.get_reply()
            if not reply or not reply.has_field("answer"):
                self._error("WebRTC did not provide an SDP answer.", generation)
                return
            answer = reply.get_value("answer")
            answer_text.append(answer.sdp.as_text())
            receiver.emit("set-local-description", answer,
                          Gst.Promise.new_with_change_func(local_set, None, None))

        def remote_set(promise, *_):
            if not reply_ok(promise):
                return
            self.remote_ready = True
            for candidate in self.pending_ice:
                receiver.emit("add-ice-candidate", candidate["sdpMLineIndex"], candidate["candidate"])
            self.pending_ice.clear()
            receiver.emit("create-answer", None,
                          Gst.Promise.new_with_change_func(answer_created, None, None))

        receiver.emit("set-remote-description", description,
                      Gst.Promise.new_with_change_func(remote_set, None, None))

    async def ice(self, candidate):
        if candidate is None:
            return

        def add():
            if self.remote_ready:
                self.webrtc.emit("add-ice-candidate", candidate["sdpMLineIndex"], candidate["candidate"])
            elif len(self.pending_ice) < 256:
                self.pending_ice.append(candidate)
            else:
                raise ValueError("Too many ICE candidates before SDP negotiation.")

        await self._run(add)

    async def stop_stream(self):
        await self._run(self._stop_stream)

    def _stop_stream(self):
        with self.lock:
            self.generation += 1
            if self.selector:
                self.selector.set_property("active-pad", self.slate)
            receiver, branch, video_pad = self.webrtc, self.branch, self.video_pad
            self.webrtc = self.branch = self.video_pad = None
            self.pending_ice.clear()
            self.remote_ready = False
            self.last_frame = 0.0
        # Never hold the Python callback lock across Gst.set_state(NULL): it
        # waits for streaming callbacks, which may themselves need this lock.
        if receiver:
            receiver.set_state(self.Gst.State.NULL)
            self.pipeline.remove(receiver)
        if branch:
            branch.set_state(self.Gst.State.NULL)
            self.pipeline.remove(branch)
        if video_pad:
            self.selector.release_request_pad(video_pad)

    def metrics(self):
        now = time.monotonic()
        previous, received, output = self.sample
        elapsed = max(now - previous, 0.001)
        values = {"state": "error" if self.fault else "live" if self.last_frame and now - self.last_frame < 3 else "waiting",
                  "incoming_fps": round((self.received - received) / elapsed, 1),
                  "output_fps": round((self.output_frames - output) / elapsed, 1),
                  "frames_received": self.received, "frames_output": self.output_frames,
                  "glass_to_glass_ms": None}
        self.sample = (now, self.received, self.output_frames)
        return values

    async def shutdown(self):
        def close():
            self._stop_stream()
            if self.watchdog_id:
                self.GLib.source_remove(self.watchdog_id)
            if self.pipeline:
                self.pipeline.set_state(self.Gst.State.NULL)
                self.bus.remove_signal_watch()
            self.mainloop.quit()

        await self._run(close)
        await asyncio.to_thread(self.thread.join, 3)
