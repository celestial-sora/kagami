"""AirPlay contracts and opt-in real RTP/H264 decoding, without an Apple device."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/receiver"))
from kagami_receiver.airplay import AirPlayTransport, AUDIO_VERSION, DISCONNECTED_EVENT, EVENTS_VERSION, capabilities, media_description, preflight
from kagami_receiver.model import FrameFormat, ReceiverError


class AirPlayContractTests(unittest.TestCase):
    def test_backend_version_and_required_flags(self):
        valid = "UxPlay 1.73.2 -vrtp -rc -as -nh -p " + EVENTS_VERSION + " " + AUDIO_VERSION
        with patch("kagami_receiver.airplay.shutil.which", return_value="/usr/bin/uxplay"), patch("kagami_receiver.airplay.command", return_value=valid) as command:
            self.assertEqual(capabilities()["version"], "UxPlay 1.73.2")
            command.assert_called_once_with(["/usr/bin/uxplay", "-rc", "/dev/null", "-h"])
        for invalid in (valid.replace("1.73.2", "1.68"), valid.replace("-vrtp", ""), valid.replace(EVENTS_VERSION, ""), valid.replace(AUDIO_VERSION, ""), "Unknown backend"):
            with patch("kagami_receiver.airplay.shutil.which", return_value="uxplay"), patch("kagami_receiver.airplay.command", return_value=invalid), self.assertRaises(ReceiverError):
                capabilities()
        with patch("kagami_receiver.airplay.shutil.which", return_value=None), self.assertRaises(ReceiverError):
            capabilities()

    def test_preflight_uses_avahi_without_wifi_direct_or_network_mutations(self):
        with patch("kagami_receiver.airplay.capabilities", return_value={"version": "UxPlay 1.73.2"}), \
                patch("kagami_receiver.airplay.subprocess.run", return_value=Mock(returncode=0, stdout="active\n")) as run, \
                patch("kagami_receiver.airplay.gst") as gst:
            gst.return_value.ElementFactory.find.return_value = True
            checks = preflight()
            self.assertTrue(all(c["ok"] for c in checks))
            run.assert_called_once_with(["systemctl", "is-active", "avahi-daemon.service"], capture_output=True, text=True, timeout=5)

    def test_preflight_reports_missing_discovery_and_decoder(self):
        with patch("kagami_receiver.airplay.capabilities", side_effect=ReceiverError("unsupported", "missing")), \
                patch("kagami_receiver.airplay.subprocess.run", return_value=Mock(returncode=3, stdout="inactive")), \
                patch("kagami_receiver.airplay.gst", side_effect=ReceiverError("decoder", "missing plugins")):
            self.assertTrue(all(not c["ok"] for c in preflight()))

    def test_preflight_reports_missing_desktop_audio_plugin(self):
        with patch("kagami_receiver.airplay.capabilities", return_value={"version": "UxPlay 1.73.2"}), \
                patch("kagami_receiver.airplay.subprocess.run", return_value=Mock(returncode=0, stdout="active\n")), \
                patch("kagami_receiver.airplay.gst") as gst:
            gst.return_value.ElementFactory.find.side_effect = lambda name: name != "pulsesink"
            checks = {c["name"]: c for c in preflight()}
            self.assertTrue(checks["airplay_decoder"]["ok"])
            self.assertFalse(checks["airplay_audio"]["ok"])
            self.assertIn("pulsesink", checks["airplay_audio"]["detail"])

    def test_ports_and_fps_are_bounded(self):
        for port in (0, 1023, 65534, "35000", True):
            with self.assertRaises(ValueError):
                AirPlayTransport(port)
        for fps in (0, 61, 30.0, True):
            with self.assertRaises(ValueError):
                media_description(fps)
        self.assertIn("address=127.0.0.1", media_description(30))
        self.assertIn("width=1280,height=720", media_description(30))

    def test_waits_for_real_frames_and_holds_ten_minutes_of_idle_video(self):
        adapter = AirPlayTransport()
        with patch("kagami_receiver.airplay.capture_format", return_value=FrameFormat(1280, 720)) as capture:
            self.assertIsNone(adapter.frame_format())
            capture.assert_not_called()
            adapter.source = "/dev/video11"
            adapter.last_frame = time.monotonic()
            self.assertEqual(adapter.frame_format(), FrameFormat(1280, 720))
            adapter.last_frame -= 600
            self.assertIsNone(adapter.failure())
        self.assertIsNone(adapter.startup_timeout)

    def test_only_exact_protocol_disconnect_event_ends_idle_video(self):
        adapter = AirPlayTransport()
        adapter.last_frame = time.monotonic() - 600
        for line in ("2 missed client feedback signals", "video paused", "prefix " + DISCONNECTED_EVENT):
            adapter._read_line(line)
            self.assertIsNone(adapter.failure())
        adapter._read_line(DISCONNECTED_EVENT + "\n")
        self.assertEqual(adapter.failure().category, "connectivity")
        adapter.stop()
        self.assertIsNone(adapter.failure())

    def test_log_storage_has_bounded_lines_and_count(self):
        adapter = AirPlayTransport()
        for _ in range(100):
            adapter._read_line("x" * 2000)
        self.assertEqual(len(adapter.logs), 20)
        self.assertTrue(all(len(line) == 1000 for line in adapter.logs))

    def test_backend_audio_failure_is_reported_and_stop_clears_it(self):
        adapter = AirPlayTransport()
        adapter._read_line("GStreamer error (audio): pulsesink Connection terminated")
        self.assertIn("sound output", str(adapter.failure()))
        adapter.stop()
        self.assertIsNone(adapter.failure())

    def test_start_failure_releases_decoder_before_returning(self):
        gst = Mock()
        gst.parse_launch.return_value.set_state.return_value = gst.StateChangeReturn.FAILURE
        adapter = AirPlayTransport()
        with patch("kagami_receiver.airplay.preflight", return_value=[]), patch("kagami_receiver.airplay.gst", return_value=gst), \
                patch("kagami_receiver.airplay.set_output_fps"), \
                patch("kagami_receiver.airplay.subprocess.Popen") as spawn, self.assertRaises(ReceiverError):
            adapter.start("/dev/video11", 30)
        spawn.assert_not_called()
        self.assertIsNone(adapter.pipeline)

    def test_real_child_uses_local_bridge_no_recording_and_is_reaped(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "uxplay"
            path.write_text("#!/bin/sh\necho listening\necho " + DISCONNECTED_EVENT + "\nexec sleep 30\n")
            path.chmod(0o755)
            gst = Mock()
            adapter = AirPlayTransport()
            try:
                with patch("kagami_receiver.airplay.preflight", return_value=[]), patch("kagami_receiver.airplay.gst", return_value=gst), \
                        patch("kagami_receiver.airplay.set_output_fps"), \
                        patch("kagami_receiver.airplay.capabilities", return_value={"binary": str(path)}):
                    adapter.start("/dev/video11", 30)
                process = adapter.process
                args = process.args
                self.assertEqual(args[1:3], ["-rc", "/dev/null"])
                self.assertIn("-vrtp", args)
                self.assertIn("host=127.0.0.1", args[-1])
                self.assertEqual(args[args.index("-as") + 1], "pulsesink client-name=Kagami")
                self.assertNotIn("-mp4", args)
                self.assertNotIn("-artp", args)
                self.assertEqual(adapter.state, "listening")
                self.assertTrue(adapter.disconnected.wait(timeout=2), "Owned child lifecycle event was not consumed")
                self.assertEqual(adapter.failure().category, "connectivity")
                with self.assertRaises(ReceiverError):
                    adapter.start("/dev/video11", 30)
                adapter.stop()
                self.assertIsNotNone(process.poll())
                self.assertIsNone(adapter.process)
                self.assertIsNone(adapter.pipeline)
            finally:
                adapter.stop()


@unittest.skipUnless(os.environ.get("KAGAMI_TEST_GST") == "1", "opt-in synthetic AirPlay RTP/H264 integration")
class AirPlayMediaTests(unittest.TestCase):
    def test_portrait_h264_decodes_into_fixed_letterboxed_canvas(self):
        from kagami_receiver.pipeline import gst, pipeline_error
        Gst = gst()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        receiver = Gst.parse_launch(media_description(10) + "videoconvert ! video/x-raw,format=RGBA ! appsink name=frames max-buffers=2 drop=true sync=false")
        receiver.get_by_name("rtp").set_property("port", port)
        sender = Gst.parse_launch('videotestsrc is-live=true pattern=smpte ! video/x-raw,width=160,height=320,framerate=10/1 ! '
                                 'x264enc tune=zerolatency key-int-max=10 ! h264parse ! rtph264pay pt=96 config-interval=1 ! '
                                 f'udpsink host=127.0.0.1 port={port} sync=false')
        try:
            self.assertNotEqual(receiver.set_state(Gst.State.PLAYING), Gst.StateChangeReturn.FAILURE)
            self.assertNotEqual(sender.set_state(Gst.State.PLAYING), Gst.StateChangeReturn.FAILURE)
            samples = []
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and len(samples) < 2:
                self.assertIsNone(pipeline_error(Gst, receiver))
                self.assertIsNone(pipeline_error(Gst, sender))
                sample = receiver.get_by_name("frames").emit("try-pull-sample", Gst.SECOND // 5)
                if sample:
                    caps = sample.get_caps().get_structure(0)
                    self.assertEqual((caps.get_value("width"), caps.get_value("height")), (1280, 720))
                    self.assertEqual(caps.get_string("format"), "RGBA")
                    pixels = sample.get_buffer().extract_dup(0, sample.get_buffer().get_size())
                    if not samples or pixels != samples[-1]:
                        samples.append(pixels)
            self.assertEqual(len(samples), 2)
            self.assertTrue(samples[0] != samples[1], "Moving source decoded as a frozen image")
            for pixels in samples:
                row = pixels[360 * 1280 * 4:361 * 1280 * 4]
                self.assertTrue(all(row[x*4] < 8 and row[x*4+1] < 8 and row[x*4+2] < 8 for x in range(0, 450)))
                self.assertGreater(sum(row[x*4] + row[x*4+1] + row[x*4+2] for x in range(480, 800)), 10000)
        finally:
            sender.set_state(Gst.State.NULL)
            receiver.set_state(Gst.State.NULL)


if __name__ == "__main__":
    unittest.main()
