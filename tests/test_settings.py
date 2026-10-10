"""Persistence/relaunch contracts, isolated from host settings and media."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/receiver"))
from kagami_receiver.model import Crop, Framing, OutputConfig
from kagami_receiver.settings import DesktopPreferences, Settings


class SettingsTests(unittest.TestCase):
    def test_installer_settings_migrate_and_explicit_choices_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps(dict(source="/dev/video21", output="/dev/video20", width=1280,
                                            height=720, fps=30, interface="wlan2", preferred_transport="airplay",
                                            future_metadata={"keep": True})))
            store = Settings(path)
            initial = store.load()
            self.assertEqual(initial.output.device, "/dev/video20")
            self.assertEqual(initial.transport, "airplay")
            framing = Framing(Crop(.1, .2, .7, .6), 270, True, "fill")
            choices = DesktopPreferences(OutputConfig("/dev/video21", "/dev/video20", 1920, 1080, 60),
                                         "wlan3", "wifi", framing, 0, "กล้องของฉัน")
            store.save(choices)
            self.assertEqual(Settings(path).load(), choices)
            data = json.loads(path.read_text())
            self.assertEqual(data["future_metadata"], {"keep": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("allow_disconnect", data)
            self.assertNotIn("pairing_code", data)
            self.assertNotIn("serial", data)

    def test_failed_atomic_replace_preserves_last_settings_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Settings(Path(directory) / "settings.json")
            store.save(DesktopPreferences())
            before = store.path.read_bytes()
            with patch("kagami_receiver.settings.Path.replace", side_effect=OSError("disk error")), self.assertRaises(OSError):
                store.save(DesktopPreferences(transport="airplay"))
            self.assertEqual(store.path.read_bytes(), before)
            self.assertEqual(list(Path(directory).glob(".settings-*.tmp")), [])

    def test_invalid_settings_are_rejected_without_rewriting_file(self):
        invalid = [[], {"fps": 0}, {"width": 1279}, {"preferred_transport": "browser"},
                   {"interface": "wlan2;bad"}, {"crop_aspect": True}, {"preset_label": 4},
                   {"framing": {"crop": asdict(Crop()), "rotation": 0, "mirror": "false", "fit": "fit"}}]
        with tempfile.TemporaryDirectory() as directory:
            store = Settings(Path(directory) / "settings.json")
            for value in invalid:
                before = json.dumps(value)
                store.path.write_text(before)
                with self.subTest(value=value), self.assertRaises(ValueError):
                    store.load()
                self.assertEqual(store.path.read_text(), before)

    def test_desktop_cli_restores_saved_values_but_explicit_flags_override(self):
        from kagami_receiver.__main__ import main
        with tempfile.TemporaryDirectory() as directory:
            store = Settings(Path(directory) / "settings.json")
            choices = DesktopPreferences(OutputConfig(width=1920, height=1080, fps=60), transport="airplay",
                                         framing=Framing(Crop(.1, .1, .8, .8), 90, True, "fill"))
            store.save(choices)
            run = Mock(return_value=0)
            for extra, expected in (([], choices.output), (["--fps", "24"], OutputConfig(width=1920, height=1080, fps=24))):
                with patch.object(sys, "argv", ["kagami", "desktop", "--settings", str(store.path), *extra]), \
                        patch("kagami_receiver.__main__.os.geteuid", return_value=1000), \
                        patch.dict(sys.modules, {"kagami_receiver.desktop": SimpleNamespace(run=run)}):
                    self.assertEqual(main(), 0)
                self.assertEqual(run.call_args.args[0], expected)
                self.assertEqual(run.call_args.kwargs["preferences"].framing, choices.framing)
                self.assertEqual(run.call_args.args[2], "airplay")


if __name__ == "__main__":
    unittest.main()
