"""Headless V2 contracts. Real raw-frame integration is opt-in via KAGAMI_TEST_GST."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/receiver")]
from kagami_receiver.model import Crop, FrameFormat, Framing, OutputConfig, Presets, ReceiverError, centered_crop, content_rect, drag_crop
from kagami_receiver.transport import Device, ScrcpyTransport, endpoint, pair, parse_devices, scrcpy_capabilities


class GeometryTests(unittest.TestCase):
    def test_crop_rejects_invalid_and_nonfinite_values(self):
        for values in ((-.1, 0, 1, 1), (0, 0, 0, 1), (.9, 0, .2, 1), (float("nan"), 0, 1, 1), (0, 0, float("inf"), 1)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Crop(*values)

    def test_crop_pixels_remain_inside_odd_source_dimensions(self):
        self.assertEqual(Crop(.2, .25, .8, .75).pixels(101, 81), (20, 20, 81, 61))
        self.assertEqual(Crop(.999, .999, .001, .001).pixels(100, 100), (99, 99, 1, 1))

    def test_presets_keep_pixel_aspect_and_center(self):
        for ratio in (16/9, 4/3, 1, 9/16):
            crop = centered_crop(1080, 1920, ratio)
            self.assertAlmostEqual(crop.width * 1080 / (crop.height * 1920), ratio)
            self.assertAlmostEqual(crop.x + crop.width / 2, .5)
            self.assertAlmostEqual(crop.y + crop.height / 2, .5)

    def test_drag_uses_letterboxed_content_and_clips_edges(self):
        rectangle = content_rect(800, 400, 200, 400)
        self.assertEqual(rectangle, (300, 0, 200, 400))
        self.assertEqual(drag_crop((100, -10), (900, 500), rectangle), Crop())
        self.assertEqual(drag_crop((450, 300), (350, 100), rectangle), Crop(.25, .25, .5, .5))
        self.assertIsNone(drag_crop((400, 200), (400, 200), rectangle))

    def test_output_rejects_same_device_injection_and_invalid_caps(self):
        for kwargs in ({"source": "/dev/video10"}, {"device": "/dev/video0; touch /tmp/x"}, {"width": 1279}, {"fps": 0}, {"height": 9999}, {"fps": 30.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                OutputConfig(**kwargs)

    def test_settings_are_local_and_keyed_by_device_label_and_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Presets(Path(directory) / "presets.json")
            framing = Framing(Crop(.1, .2, .7, .6), 90, True, "fill")
            frame = FrameFormat(1080, 1920)
            store.save("serial", "Samsung Camera", frame, framing)
            self.assertEqual(store.load("serial", "Samsung Camera", frame), framing)
            self.assertEqual(store.load("serial", "Samsung Camera", FrameFormat(1920, 1080)), Framing())
            self.assertEqual(store.load("other", "Samsung Camera", frame), Framing())
            self.assertEqual(store.load("serial", "TikTok", frame), Framing())
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("pixels", store.path.read_text())


class TransportTests(unittest.TestCase):
    def test_device_states_and_connection_kinds(self):
        rows = parse_devices("List of devices attached\nUSB1 device usb:1-2 model:SM_S921B transport_id:1\nUSB2 unauthorized usb:1-3\n192.168.1.2:37123 device model:Galaxy\nadb-ABC._adb-tls-connect._tcp device model:Galaxy\nOFF offline\n")
        self.assertEqual([d.connection for d in rows], ["usb", "usb", "wifi", "wifi", "unknown"])
        self.assertEqual(rows[0].model, "SM S921B")
        self.assertEqual(rows[1].state, "unauthorized")

    def test_wireless_endpoint_is_explicit_private_and_valid(self):
        self.assertEqual(endpoint("192.168.1.4:37123"), "192.168.1.4:37123")
        self.assertEqual(endpoint("[fd12::1]:5555"), "[fd12::1]:5555")
        for value in ("example.com:5555", "8.8.8.8:5555", "127.0.0.1:5555", "0.0.0.0:5555", "192.168.1.4:0", "192.168.1.4:65536", "192.168.1.4:5555;id"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                endpoint(value)

    def test_pairing_secret_is_sent_via_stdin(self):
        with patch("kagami_receiver.transport.command", return_value="Successfully paired to 192.168.1.4") as run:
            pair("192.168.1.4:12345", "123456")
            args, kwargs = run.call_args
            self.assertNotIn("123456", args[0])
            self.assertEqual(kwargs["input"], "123456\n")
        with self.assertRaises(ValueError):
            pair("192.168.1.4:12345", "secret")

    def test_scrcpy_version_and_required_flags_are_verified(self):
        flags = "--v4l2-sink --no-video-playback --no-audio --no-control --capture-orientation --max-size --max-fps"
        with patch("kagami_receiver.transport.command", side_effect=["scrcpy 3.3.4\n", flags]):
            self.assertEqual(scrcpy_capabilities(), "scrcpy 3.3.4")
        for version, help_text in (("scrcpy 2.7", flags), ("scrcpy 3.3", "--no-audio"), ("unknown", flags)):
            with patch("kagami_receiver.transport.command", side_effect=[version, help_text]), self.assertRaises(ReceiverError):
                scrcpy_capabilities()

    def test_unauthorized_phone_is_actionable_and_never_spawned(self):
        device = Device("USB1", "unauthorized", "Galaxy", "usb")
        with patch("kagami_receiver.transport.devices", return_value=[device]), patch("kagami_receiver.transport.subprocess.Popen") as spawn:
            with self.assertRaises(ReceiverError) as error:
                ScrcpyTransport(device).start("/dev/video11", 30)
            self.assertEqual(error.exception.category, "permission")
            spawn.assert_not_called()

    def test_mode_mismatch_does_not_switch_networks(self):
        device = Device("192.168.1.4:5555", "device", "Galaxy", "wifi")
        with patch("kagami_receiver.transport.devices", return_value=[device]), self.assertRaises(ReceiverError):
            ScrcpyTransport(device, "usb").start("/dev/video11", 30)
        with self.assertRaises(ReceiverError):
            ScrcpyTransport(device, "miracast")

    def test_scrcpy_uses_only_screen_sink_and_stop_reaps_real_child(self):
        device = Device("USB1", "device", "Galaxy", "usb")
        real_popen = subprocess.Popen
        launched = []
        def spawn(args, **kwargs):
            launched.extend(args)
            return real_popen([sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(60)"], **kwargs)
        with patch("kagami_receiver.transport.devices", return_value=[device]), patch("kagami_receiver.transport.scrcpy_capabilities", return_value="scrcpy 3.3"), patch("kagami_receiver.transport.subprocess.Popen", side_effect=spawn):
            adapter = ScrcpyTransport(device)
            adapter.start("/dev/video11", 30)
            process = adapter.process
            self.assertIn("--capture-orientation=@", launched)
            self.assertIn("--no-audio", launched)
            self.assertIn("--no-control", launched)
            self.assertFalse(any("camera" in flag or "record" in flag for flag in launched))
            self.assertIsNone(adapter.failure())
            adapter.stop()
            adapter.stop()
            self.assertIsNotNone(process.poll())
            self.assertEqual(adapter.state, "stopped")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        from kagami_receiver.controller import Receiver
        self.receiver = Receiver(OutputConfig())
        self.transport = Mock()
        self.transport.failure.return_value = None

    def tearDown(self):
        self.receiver.stop()

    def test_partial_start_failure_cleans_writer_and_transport(self):
        with patch.object(self.receiver, "_lock_devices"), patch("kagami_receiver.controller.query_device"), patch("kagami_receiver.controller.CameraOutput") as output:
            self.transport.start.side_effect = ReceiverError("permission", "unauthorized")
            with self.assertRaises(ReceiverError):
                self.receiver.start(self.transport)
            output.return_value.stop.assert_called_once()
            self.transport.stop.assert_called_once()
            self.assertEqual(self.receiver.state, "stopped")

    def test_disconnect_keeps_writer_and_slate_until_explicit_stop(self):
        with patch.object(self.receiver, "_lock_devices"), patch("kagami_receiver.controller.query_device"), patch("kagami_receiver.controller.CameraOutput") as output:
            writer = output.return_value
            writer.error.return_value = None
            self.receiver.start(self.transport)
            self.transport.failure.return_value = ReceiverError("connectivity", "USB disconnected")
            self.receiver.tick()
            writer.slate.assert_called_once()
            writer.stop.assert_not_called()
            self.assertEqual(self.receiver.state, "disconnected")
            self.receiver.stop()
            writer.stop.assert_called_once()

    def test_loopback_ownership_cannot_be_shared(self):
        from kagami_receiver.controller import Receiver
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
            other = Receiver(OutputConfig())
            self.receiver._lock_devices()
            try:
                with self.assertRaises(ReceiverError):
                    other._lock_devices()
            finally:
                other.stop()


@unittest.skipUnless(os.environ.get("KAGAMI_TEST_GST") == "1", "opt-in real GStreamer raw-frame integration")
class RawFrameIntegrationTests(unittest.TestCase):
    def setUp(self):
        from kagami_receiver.pipeline import gst
        self.Gst = gst()
        self.config = OutputConfig(width=64, height=64, fps=10)
        self.frame = FrameFormat(80, 60)

    def exercise(self, framing):
        from kagami_receiver.pipeline import CameraOutput, Processor
        Gst = self.Gst
        output = CameraOutput(self.config, test_sink="appsink name=consumer max-buffers=2 drop=true sync=false")
        processor = Processor(self.frame, framing, self.config, output, test_source='appsrc name=test is-live=true format=time do-timestamp=true caps="video/x-raw,format=RGBA,width=80,height=60,framerate=10/1,pixel-aspect-ratio=1/1"')
        try:
            output.start()
            consumer = output.pipeline.get_by_name("consumer")
            slate = consumer.emit("try-pull-sample", Gst.SECOND)
            self.assertIsNotNone(slate)
            slate_caps = slate.get_caps()
            processor.start()
            pixels = b"".join(bytes(((255, 0, 0, 255) if x < 40 else (0, 255, 0, 255)) if y < 30 else ((0, 0, 255, 255) if x < 40 else (255, 255, 0, 255))) for y in range(60) for x in range(80))
            source = processor.pipeline.get_by_name("test")
            result = None
            for index in range(20):
                buffer = Gst.Buffer.new_allocate(None, len(pixels), None)
                buffer.fill(0, pixels)
                buffer.duration = Gst.SECOND // 10
                self.assertEqual(source.emit("push-buffer", buffer), Gst.FlowReturn.OK)
                time.sleep(.025)
                self.assertIsNone(processor.error())
                self.assertIsNone(output.error())
                if "processed" in (previews := processor.take_previews()):
                    result = previews["processed"]
                    break
            self.assertIsNotNone(result, "processed raw frames did not arrive")
            self.assertEqual(result[:2], (64, 64))
            consumer = output.pipeline.get_by_name("consumer")
            sample = consumer.emit("try-pull-sample", Gst.SECOND)
            self.assertIsNotNone(sample, "persistent output produced no sample")
            self.assertEqual(sample.get_caps().get_structure(0).get_string("format"), "YUY2")
            # Verify transformed video reaches the persistent writer, then black
            # replaces it. Merely seeing negotiated caps would also pass a slate.
            center_offset = (32 * 64 + 32) * 2
            for _ in range(15):
                sample = consumer.emit("try-pull-sample", Gst.SECOND // 5)
                if sample and sample.get_buffer().extract_dup(center_offset, 1)[0] > 20:
                    break
            else:
                self.fail("transformed signal never reached the YUY2 output")
            self.assertGreater(output.frames, 0)
            self.assertTrue(sample.get_caps().is_equal(slate_caps),
                            "Slate/live switch renegotiated the consumer's camera caps")
            self.assertGreater(processor.metrics()["frames_processed"], 0)
            writer = output.pipeline
            processor.stop()
            output.slate()
            self.assertIs(output.pipeline, writer)
            for _ in range(15):
                sample = consumer.emit("try-pull-sample", Gst.SECOND // 5)
                if sample and sample.get_buffer().extract_dup(center_offset, 1)[0] <= 20:
                    break
            else:
                self.fail("no-signal slate did not replace the live output")
            processor.start()
            self.assertIs(output.pipeline, writer)
            return result[2]
        finally:
            processor.stop()
            output.stop()

    @staticmethod
    def pixel(pixels, x, y):
        offset = (y * 64 + x) * 4
        return tuple(pixels[offset:offset+3])

    def test_manual_crop_reaches_processed_output(self):
        pixels = self.exercise(Framing(Crop(0, .5, .5, .5), fit="fill"))
        self.assertEqual(self.pixel(pixels, 32, 32), (0, 0, 255))

    def test_rotation_and_mirror_order(self):
        pixels = self.exercise(Framing(rotation=90, mirror=True, fit="fill"))
        self.assertEqual(self.pixel(pixels, 16, 16), (255, 0, 0))
        self.assertEqual(self.pixel(pixels, 48, 16), (0, 0, 255))

    def test_fit_adds_black_borders_without_stretching(self):
        pixels = self.exercise(Framing())
        self.assertEqual(self.pixel(pixels, 32, 0), (0, 0, 0))
        self.assertEqual(self.pixel(pixels, 16, 16), (255, 0, 0))

    def test_fill_and_all_rotation_caps(self):
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                self.exercise(Framing(rotation=rotation, fit="fill"))


class SetupHelperTests(unittest.TestCase):
    def test_two_device_preflight_rejects_same_slots_and_unsafe_numbers(self):
        helper = ROOT / "packaging/fedora/kagami-receiver-camera-setup"
        for args in (("10", "10"), ("256", "11"), ("10", "11;id"), ("-1", "11")):
            result = subprocess.run(["bash", str(helper), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_existing_helper_rejects_unrecognized_label(self):
        result = subprocess.run(["bash", str(ROOT / "packaging/fedora/kagami-camera-setup"), "10", "Physical Camera"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
