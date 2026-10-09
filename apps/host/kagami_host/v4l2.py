"""Reject physical cameras before allowing a writer to open its output device."""

import fcntl
import os
import struct

# linux/videodev2.h: struct v4l2_capability (104 bytes), VIDIOC_QUERYCAP.
VIDIOC_QUERYCAP = 0x80685600
CAPABILITY = struct.Struct("16s32s32sIII3I")


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
