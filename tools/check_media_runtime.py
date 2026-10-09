#!/usr/bin/env python3
"""Validate GStreamer plugins/ICE APIs without claiming V4L2 hardware proof."""
from kagami_host.media import gst_modules

_glib, Gst, _sdp, _webrtc = gst_modules()
receiver = Gst.ElementFactory.make("webrtcbin", "api-check")
ice = receiver.get_property("ice-agent")
ice.set_property("min-rtp-port", 50000)
ice.set_property("max-rtp-port", 50100)
assert ice.get_property("min-rtp-port") == 50000
assert ice.get_property("max-rtp-port") == 50100
print(f"{Gst.version_string()}: required plugins and bounded ICE port APIs passed. No device, stream or OBS test performed.")
