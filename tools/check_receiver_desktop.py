#!/usr/bin/env python3
"""Real GTK window/crop smoke check under Xvfb; never captures a phone."""
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "apps/receiver")]
from kagami_receiver.desktop import GLib, Gtk, Window
from gi.repository import Gio
from kagami_receiver.model import Crop, FrameFormat, OutputConfig
from kagami_receiver.settings import Settings

app = Gtk.Application(application_id="io.kagami.ReceiverSmoke", flags=Gio.ApplicationFlags.NON_UNIQUE)
errors = []
checks_ran = []
temporary = tempfile.TemporaryDirectory(prefix="kagami-desktop-qa-")
settings = Settings(Path(temporary.name) / "settings.json")


def activate(application):
    window = Window(application, OutputConfig(), "wlan2", "airplay", settings=settings)
    window.set_default_size(920, 520)
    window.present()
    def check():
        try:
            assert window.interface.get_text() == "wlan2"
            assert window.mode.get_selected() == 1
            assert window.start.get_label() == "Start AirPlay"
            assert window.start.get_parent().get_parent() == window.get_child()
            assert window.status.get_parent().has_css_class("status-panel")
            assert window.source_cards[0][0].has_css_class("selected")
            window.source_cards[1][0].emit("clicked")
            assert window.mode.get_selected() == 0
            assert window.source_cards[1][0].has_css_class("selected")
            window.source_cards[0][0].emit("clicked")
            window.guide.set_active(True)
            window.safe_area.set_active(True)
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
            window.fps.set_value(60)
            window.rotation.set_selected(1)
            window.mirror.set_active(True)
            window.fit.set_selected(1)
            window.crop = Crop(.1, .2, .7, .6)
            window.apply_framing()
            framing = window.framing()
            with patch.object(Receiver, "start", lambda _, transport: starts.append(transport)):
                window.start_receiver(None)
            assert len(starts) == 1 and starts[0].identity.connection == "airplay"
            assert "Screen Mirroring" in window.status.get_text()
            assert (window.receiver.config.width, window.receiver.config.height) == (1920, 1080)
            assert window.receiver.framing == framing
            window.stop_receiver(None)
            with patch.object(Receiver, "start", lambda _, transport: starts.append(transport)):
                window.start_receiver(None)
            assert window.receiver.framing == framing
            restored = Window(application, OutputConfig(), settings=settings)
            assert restored.receiver.config == window.receiver.config
            assert restored.framing() == framing
            assert restored.mode.get_selected() == 1
            assert restored.fps.get_value_as_int() == 60
            assert restored.interface.get_text() == "wlan2"
            assert not restored.allow_disconnect.get_active()
            assert restored.code.get_text() == ""
            assert restored.receiver.state == "stopped"
            restored.close_window(restored)
            restored.destroy()
            bad_path = Path(temporary.name) / "invalid.json"
            bad_path.write_text("{incomplete")
            invalid = Window(application, OutputConfig(), settings=Settings(bad_path))
            assert "could not load" in invalid.settings_status.get_text()
            invalid.close_window(invalid)
            invalid.destroy()
            assert bad_path.read_text() == "{incomplete"
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
            window.interface.set_text("wlan3")
            window.app_name.set_text("Remember this label")
            window.allow_disconnect.set_active(True)
            window.code.set_text("123456")
        except Exception as exc:
            errors.append(repr(exc))
        def check_autosave():
            checks_ran.append(True)
            try:
                saved = settings.load()
                assert saved.interface == "wlan3"
                assert saved.transport == "wifi"
                assert saved.label == "Remember this label"
                assert "123456" not in settings.path.read_text()
                restored = Window(application, OutputConfig(), settings=settings)
                assert restored.mode.get_selected() == 3
                assert not restored.allow_disconnect.get_active()
                assert restored.code.get_text() == ""
                restored.close_window(restored)
                restored.destroy()
            except Exception as exc:
                errors.append("Autosave: " + repr(exc))
            window.close()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(600, check_autosave)
        return GLib.SOURCE_REMOVE
    GLib.timeout_add(300, check)


app.connect("activate", activate)
status = app.run([])
temporary.cleanup()
if status or errors or not checks_ran:
    raise SystemExit("GTK smoke check failed: " + "; ".join(errors))
print("GTK4 receiver controls, autosave/reopen, retained Start framing and stop/close passed (no hardware).")
