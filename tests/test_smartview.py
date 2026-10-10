"""Smart View preflight/broker boundaries and real synthetic Miracast media."""
import os
from pathlib import Path
import runpy
import socket
import sys
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/receiver")]
from kagami_receiver.model import ReceiverError
from kagami_receiver.smartview import SmartViewTransport, interface_modes, interface_name, media_description, preflight


class SmartViewContractTests(unittest.TestCase):
    def test_p2p_capability_checks_only_supported_modes(self):
        # Some drivers mention P2P in TX/RX capabilities despite not exposing it.
        text = "Supported interface modes:\n\t * managed\n\t * AP\nBand 1:\nSupported TX frame types:\n\t * P2P-client: 0x40\n\t * P2P-GO: 0x40\n"
        self.assertEqual(interface_modes(text), {"managed", "AP"})
        text = "Supported interface modes:\n\t * managed\n\t * P2P-client\n\t * P2P-GO\n\t * P2P-device\nBand 1:\n"
        self.assertTrue({"P2P-client", "P2P-GO"}.issubset(interface_modes(text)))

    def test_preflight_reports_unsupported_adapter_without_mutating_network(self):
        with patch("kagami_receiver.smartview.command", side_effect=["Interface wlo1\n wiphy 0", "Supported interface modes:\n * managed\nBand 1:\n"]), patch("kagami_receiver.smartview.shutil.which", return_value=None), patch("kagami_receiver.smartview.gst") as gst:
            gst.return_value.ElementFactory.find.return_value = True
            checks = preflight("wlo1")
            self.assertFalse(checks[0]["ok"])
            self.assertIn("P2P-client/P2P-GO", checks[0]["detail"])

    def test_interface_rejects_path_and_shell_injection(self):
        self.assertEqual(interface_name("wlp3s0"), "wlp3s0")
        for value in ("../net", "wlo1;id", "-wlo1", "wlo1\n", "x" * 16):
            with self.assertRaises(ValueError):
                interface_name(value)

    def test_smartview_needs_explicit_adapter_disconnect_consent(self):
        with patch("kagami_receiver.smartview.preflight", return_value=[]), patch("kagami_receiver.smartview.subprocess.Popen") as spawn:
            with self.assertRaises(ReceiverError) as error:
                SmartViewTransport("wlo1").start("/dev/video11", 30)
            self.assertEqual(error.exception.category, "permission")
            spawn.assert_not_called()

    def test_stop_closes_privileged_control_pipe_and_decoder(self):
        adapter = SmartViewTransport("wlo1")
        adapter.Gst = Mock()
        adapter.pipeline, adapter.process = Mock(), Mock()
        process, pipeline = adapter.process, adapter.pipeline
        adapter.stop()
        process.stdin.close.assert_called_once()
        process.wait.assert_called_once_with(timeout=15)
        pipeline.set_state.assert_called_once()
        self.assertEqual(adapter.state, "stopped")

    def test_network_broker_rejects_normal_user_before_mutations(self):
        namespace = runpy.run_path(str(ROOT / "packaging/ubuntu/kagami-smartview-helper"))
        with patch("os.geteuid", return_value=1000), patch("subprocess.run") as run, self.assertRaises(ValueError):
            namespace["main"]()
        run.assert_not_called()

    def test_broker_rejects_unsafe_interface_before_network_commands(self):
        namespace = runpy.run_path(str(ROOT / "packaging/ubuntu/kagami-smartview-helper"))
        with patch("os.geteuid", return_value=0), patch.object(sys, "argv", ["helper", "wlo1;id"]), patch("subprocess.run") as run, self.assertRaises(ValueError):
            namespace["main"]()
        run.assert_not_called()


@unittest.skipUnless(os.environ.get("KAGAMI_TEST_GST") == "1", "opt-in synthetic Miracast RTP/H264 integration")
class SmartViewMediaTests(unittest.TestCase):
    def test_rtp_mpegts_h264_decodes_real_moving_raw_frames(self):
        from kagami_receiver.pipeline import gst, pipeline_error
        Gst = gst()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        receiver = Gst.parse_launch(media_description() + "videoconvert ! video/x-raw,format=RGBA ! appsink name=frames max-buffers=2 drop=true sync=false")
        receiver.get_by_name("rtp").set_property("port", port)
        receiver.get_by_name("rtp").set_property("address", "127.0.0.1")
        sender = Gst.parse_launch('videotestsrc is-live=true pattern=ball ! video/x-raw,width=160,height=120,framerate=10/1 ! '
                                 'x264enc tune=zerolatency key-int-max=10 ! h264parse ! mpegtsmux ! rtpmp2tpay pt=33 ! '
                                 f'udpsink host=127.0.0.1 port={port} sync=false')
        try:
            self.assertNotEqual(receiver.set_state(Gst.State.PLAYING), Gst.StateChangeReturn.FAILURE)
            self.assertNotEqual(sender.set_state(Gst.State.PLAYING), Gst.StateChangeReturn.FAILURE)
            sink = receiver.get_by_name("frames")
            samples = []
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and len(samples) < 2:
                self.assertIsNone(pipeline_error(Gst, receiver))
                self.assertIsNone(pipeline_error(Gst, sender))
                sample = sink.emit("try-pull-sample", Gst.SECOND // 5)
                if sample:
                    caps = sample.get_caps().get_structure(0)
                    self.assertEqual((caps.get_value("width"), caps.get_value("height")), (160, 120))
                    self.assertEqual(caps.get_string("format"), "RGBA")
                    samples.append(sample.get_buffer().extract_dup(0, sample.get_buffer().get_size()))
            self.assertEqual(len(samples), 2, "Miracast media path did not decode frames")
            self.assertNotEqual(samples[0], samples[1], "moving source decoded as a frozen image")
        finally:
            sender.set_state(Gst.State.NULL)
            receiver.set_state(Gst.State.NULL)


if __name__ == "__main__":
    unittest.main()
