#!/usr/bin/env python3
"""Real GTK window/crop smoke check under Xvfb; never captures a phone."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "apps/receiver"), str(root / "apps/host")]
from kagami_receiver.desktop import GLib, Gtk, Window
from kagami_receiver.model import FrameFormat, OutputConfig

app = Gtk.Application(application_id="io.kagami.ReceiverSmoke")
errors = []


def activate(application):
    window = Window(application, OutputConfig())
    window.present()
    def check():
        try:
            window.frame = FrameFormat(1080, 1920)
            window.drag_begin(None, 160, 80)
            window.drag_update(None, 200, 180)
            window.drawing.queue_draw()
            window.preset_crop()
            assert window.receiver.state == "stopped"
            assert window.stop.get_sensitive() is False
            window.stop_receiver(None)
        except Exception as exc:
            errors.append(str(exc))
        GLib.timeout_add(200, lambda: (window.close(), GLib.SOURCE_REMOVE)[1])
        return GLib.SOURCE_REMOVE
    GLib.timeout_add(300, check)


app.connect("activate", activate)
status = app.run([])
if status or errors:
    raise SystemExit("GTK smoke check failed: " + "; ".join(errors))
print("GTK4 receiver window, crop controls and stop/close passed (no hardware).")
