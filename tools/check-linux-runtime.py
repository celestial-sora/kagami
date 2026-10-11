#!/usr/bin/env python3
"""Read-only distribution CI runtime check; no phones, services or camera nodes."""
import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import Gtk, Gst

Gst.init(None)
assert (Gtk.get_major_version(), Gtk.get_minor_version()) >= (4, 8)
assert Gst.version()[:2] >= (1, 22)
from kagami_receiver.airplay import MEDIA_PLUGINS, AUDIO_PLUGINS
from kagami_receiver.smartview import MEDIA_PLUGINS as SMART_PLUGINS
missing = [name for name in set(MEDIA_PLUGINS + AUDIO_PLUGINS + SMART_PLUGINS +
           ('appsrc', 'appsink', 'v4l2sink', 'videoflip', 'videocrop', 'videoconvert', 'videoscale', 'videorate'))
           if not Gst.ElementFactory.find(name)]
from kagami_receiver.pipeline import h264_decoder
decoder = h264_decoder(Gst)
assert not missing, 'Missing: ' + ', '.join(sorted(missing))
print(f'GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, {Gst.version_string()}: bindings and receiver plugins ready')

if '--synthetic-h264' in sys.argv:
    encoder = 'openh264enc' if Gst.ElementFactory.find('openh264enc') else 'x264enc'
    pipeline = Gst.parse_launch(f'videotestsrc num-buffers=5 ! video/x-raw,format=I420,width=320,height=240,framerate=10/1 ! {encoder} ! h264parse ! video/x-h264,stream-format=byte-stream,alignment=au ! {decoder} ! appsink name=decoded max-buffers=1 drop=true sync=false wait-on-eos=false')
    try:
        pipeline.set_state(Gst.State.PLAYING)
        message = pipeline.get_bus().timed_pop_filtered(10 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
        assert message and message.type == Gst.MessageType.EOS, str(message.parse_error() if message else 'H.264 decode timeout')
        sample = pipeline.get_by_name('decoded').emit('try-pull-sample', Gst.SECOND)
        assert sample and sample.get_buffer().get_size() == 320 * 240 * 3 // 2
        print(f'Actual in-memory H.264 encode/decode passed: {encoder} → {decoder}')
    finally:
        pipeline.set_state(Gst.State.NULL)
