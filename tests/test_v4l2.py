"""Loopback interval repair and the physical-camera write guard."""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/receiver"))
from kagami_receiver.v4l2 import set_output_fps, VIDIOC_S_PARM


class LoopbackIntervalTests(unittest.TestCase):
    def test_output_interval_uses_a_valid_fraction_and_writer_type(self):
        with patch("kagami_receiver.v4l2.query_device"), \
                patch("kagami_receiver.v4l2.os.open", return_value=42), \
                patch("kagami_receiver.v4l2.os.close") as close, \
                patch("kagami_receiver.v4l2.fcntl.ioctl") as ioctl:
            set_output_fps("/dev/video10", 30)
            fd, request, parameters, mutate = ioctl.call_args.args
            self.assertEqual((fd, request, mutate), (42, VIDIOC_S_PARM, True))
            self.assertEqual(struct.unpack_from("I", parameters)[0], 2)
            self.assertEqual(struct.unpack_from("II", parameters, 12), (1, 30))
            close.assert_called_once_with(42)

    def test_rejects_physical_camera_before_interval_write(self):
        with patch("kagami_receiver.v4l2.query_device", side_effect=ValueError("physical camera")), \
                patch("kagami_receiver.v4l2.fcntl.ioctl") as ioctl:
            with self.assertRaises(ValueError):
                set_output_fps("/dev/video0", 30)
            ioctl.assert_not_called()
