#!/usr/bin/env python3
"""Read-only distribution CI runtime check; no phones, services or camera nodes."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import Gtk, Gst

Gst.init(None)
assert (Gtk.get_major_version(), Gtk.get_minor_version()) >= (4, 8)
assert Gst.version()[:2] >= (1, 20)
from kagami_receiver.airplay import MEDIA_PLUGINS, AUDIO_PLUGINS
from kagami_receiver.smartview import MEDIA_PLUGINS as SMART_PLUGINS
missing = [name for name in set(MEDIA_PLUGINS + AUDIO_PLUGINS + SMART_PLUGINS +
           ('appsrc', 'appsink', 'v4l2sink', 'videoflip', 'videocrop', 'videoconvert', 'videoscale', 'videorate'))
           if not Gst.ElementFactory.find(name)]
assert not missing, 'Missing: ' + ', '.join(sorted(missing))
print(f'GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, {Gst.version_string()}: bindings and receiver plugins ready')
