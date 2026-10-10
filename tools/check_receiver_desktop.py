#!/usr/bin/env python3
"""Real GTK window/crop smoke check under Xvfb; never captures a phone."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "apps/receiver")]
from kagami_receiver.desktop import GLib, Gtk, Window
from kagami_receiver.model import FrameFormat, OutputConfig

app = Gtk.Application(application_id="io.kagami.ReceiverSmoke")
errors = []


def activate(application):
    window = Window(application, OutputConfig(), "wlan2", "airplay")
    window.set_default_size(920, 520)
    window.present()
    def check():
        try:
            assert window.interface.get_text() == "wlan2"
            assert window.mode.get_selected() == 1
            assert window.start.get_label() == "Start AirPlay"
            assert window.start.get_parent().get_parent() == window.get_child()
            assert window.status.get_parent() == window.get_child()
            visible, bounds = window.start.compute_bounds(window)
            assert visible and bounds.get_y() >= 0
            assert bounds.get_y() + bounds.get_height() <= window.get_height()
            assert window.transport_panels[1].get_visible()
            assert not window.transport_panels[0].get_visible()
            assert not window.device.get_visible()
            # AirPlay must start without any ADB device; use a recording receiver.
            starts = []
            window.run_task = lambda task, complete: (task(), complete(None))
            from kagami_receiver.controller import Receiver
            from unittest.mock import patch
            window.size.set_selected(window.sizes.index((1920, 1080)))
            with patch.object(Receiver, "start", lambda _, transport: starts.append(transport)):
                window.start_receiver(None)
            assert len(starts) == 1 and starts[0].identity.connection == "airplay"
            assert "Screen Mirroring" in window.status.get_text()
            assert (window.receiver.config.width, window.receiver.config.height) == (1920, 1080)
            window.mode.set_selected(3)
            assert window.transport_panels[2].get_visible()
            assert window.device.get_visible()
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
