"""Decoder availability and pipeline selection across distribution codec packages."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/receiver'))
from kagami_receiver.pipeline import h264_decoder
from kagami_receiver.airplay import media_description as airplay
from kagami_receiver.smartview import media_description as smartview


class H264DecoderTests(unittest.TestCase):
    def test_prefers_libav_and_falls_back_to_openh264(self):
        for available, expected in (({'avdec_h264', 'openh264dec'}, 'avdec_h264'),
                                    ({'openh264dec'}, 'openh264dec')):
            Gst = SimpleNamespace(ElementFactory=SimpleNamespace(find=lambda name: name in available))
            self.assertEqual(h264_decoder(Gst), expected)
        Gst = SimpleNamespace(ElementFactory=SimpleNamespace(find=lambda name: False))
        with self.assertRaisesRegex(RuntimeError, 'Fedora'):
            h264_decoder(Gst)

    def test_selected_decoder_receives_access_unit_byte_stream_and_rejects_injection(self):
        for describe in (lambda decoder: airplay(30, decoder), smartview):
            pipeline = describe('openh264dec')
            self.assertIn('video/x-h264,stream-format=byte-stream,alignment=au ! openh264dec', pipeline)
            self.assertNotIn('avdec_h264', pipeline)
            with self.assertRaises(ValueError):
                describe('openh264dec ! filesink location=/tmp/screen')


@unittest.skipUnless(os.environ.get('KAGAMI_TEST_GST') == '1', 'opt-in synthetic OpenH264 decoding')
class OpenH264MediaTests(unittest.TestCase):
    def test_openh264_really_decodes_bounded_in_memory_frames(self):
        from kagami_receiver.pipeline import gst
        Gst = gst()
        pipeline = Gst.parse_launch('videotestsrc num-buffers=5 ! video/x-raw,format=I420,width=320,height=240,framerate=10/1 ! openh264enc ! h264parse ! video/x-h264,stream-format=byte-stream,alignment=au ! openh264dec ! appsink name=decoded max-buffers=1 drop=true sync=false wait-on-eos=false')
        try:
            pipeline.set_state(Gst.State.PLAYING)
            message = pipeline.get_bus().timed_pop_filtered(10 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            self.assertIsNotNone(message)
            self.assertEqual(message.type, Gst.MessageType.EOS)
            sample = pipeline.get_by_name('decoded').emit('try-pull-sample', Gst.SECOND)
            self.assertIsNotNone(sample)
            self.assertEqual(sample.get_buffer().get_size(), 320 * 240 * 3 // 2)
        finally:
            pipeline.set_state(Gst.State.NULL)
