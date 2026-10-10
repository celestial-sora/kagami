"""Reject physical cameras before allowing a writer to open its output device."""

import fcntl
import os
import struct

# linux/videodev2.h: struct v4l2_capability (104 bytes), VIDIOC_QUERYCAP.
VIDIOC_QUERYCAP = 0x80685600
CAPABILITY = struct.Struct("16s32s32sIII3I")
VIDIOC_S_PARM = 0xC0CC5616


def query_device(path):
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        data = bytearray(CAPABILITY.size)
        fcntl.ioctl(fd, VIDIOC_QUERYCAP, data, True)
    finally:
        os.close(fd)
    fields = CAPABILITY.unpack(data)
    driver, card = (value.split(b"\0", 1)[0].decode("utf-8", errors="replace") for value in fields[:2])
    if driver != "v4l2 loopback" or "Kagami" not in card:
        raise ValueError("Selected device is not a Kagami v4l2loopback device. Check docs/fedora-setup.md.")
    return {"device": path, "driver": driver, "card": card}


def set_output_fps(path, fps):
    """Reset the named loopback's interval before GStreamer probes its caps.

    A consumer can leave a different interval behind. v4l2loopback advertises
    that fixed interval while a capture client is open, preventing negotiation.
    Use OUTPUT on this new writer handle, including when a consumer is open.
    """
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("Use 1–60 FPS.")
    query_device(path)
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        parameters = bytearray(204)  # struct v4l2_streamparm, linux/videodev2.h
        struct.pack_into("I", parameters, 0, 2)  # V4L2_BUF_TYPE_VIDEO_OUTPUT
        struct.pack_into("II", parameters, 12, 1, fps)
        fcntl.ioctl(fd, VIDIOC_S_PARM, parameters, True)
    finally:
        os.close(fd)
