#!/usr/bin/env python3
"""Validate GStreamer plugins/ICE APIs without claiming V4L2 hardware proof."""
import gc

from kagami_host.media import configure_ice_ports, gst_modules

_glib, Gst, _sdp, _webrtc = gst_modules()
for index in range(3):
    receiver = Gst.ElementFactory.make("webrtcbin", f"api-check-{index}")
    ice = configure_ice_ports(receiver, 50000, 50100)
    assert ice.get_property("min-rtp-port") == 50000
    assert ice.get_property("max-rtp-port") == 50100
    watch = ice.weak_ref()
    del ice
    receiver.set_state(Gst.State.NULL)
    del receiver
    gc.collect()
    assert watch() is None, "ICE agent survived receiver teardown"
print(f"{Gst.version_string()}: required plugins, bounded ICE APIs and three clean receiver teardowns passed. No device, stream or OBS test performed.")
