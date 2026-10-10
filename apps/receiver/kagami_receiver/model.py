"""Transport-independent framing, geometry and local settings."""

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import re


class ReceiverError(RuntimeError):
    def __init__(self, category, message):
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class FrameFormat:
    width: int
    height: int
    pixel_format: str = "RGBA"
    orientation: int = 0


@dataclass(frozen=True)
class Crop:
    x: float = 0
    y: float = 0
    width: float = 1
    height: float = 1

    def __post_init__(self):
        values = (self.x, self.y, self.width, self.height)
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise ValueError("Crop coordinates must be finite numbers.")
        if min(self.x, self.y) < 0 or min(self.width, self.height) <= 0:
            raise ValueError("Crop must have positive dimensions inside the screen.")
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Crop extends outside the screen.")

    def pixels(self, width, height):
        # Convert to RGB before cropping, so odd crop coordinates are supported.
        x = min(int(self.x * width), width - 1)
        y = min(int(self.y * height), height - 1)
        w = max(1, min(round(self.width * width), width - x))
        h = max(1, min(round(self.height * height), height - y))
        return x, y, w, h


@dataclass(frozen=True)
class Framing:
    crop: Crop = Crop()
    rotation: int = 0
    mirror: bool = False
    fit: str = "fit"

    def __post_init__(self):
        if self.rotation not in (0, 90, 180, 270) or self.fit not in ("fit", "fill"):
            raise ValueError("Use quarter-turn rotation and fit or fill.")


@dataclass(frozen=True)
class OutputConfig:
    source: str = "/dev/video11"
    device: str = "/dev/video10"
    width: int = 1280
    height: int = 720
    fps: int = 30

    def __post_init__(self):
        for node in (self.source, self.device):
            if not re.fullmatch(r"/dev/video[0-9]{1,3}", node):
                raise ValueError("Select an actual /dev/videoN node.")
        if self.source == self.device:
            raise ValueError("Input and output must use two different loopback devices.")
        if not all(type(v) is int for v in (self.width, self.height, self.fps)):
            raise ValueError("Output dimensions and FPS must be integers.")
        if not (16 <= self.width <= 3840 and 16 <= self.height <= 3840):
            raise ValueError("Output dimensions must be between 16 and 3840.")
        if self.width % 2 or self.height % 2 or not 1 <= self.fps <= 60:
            raise ValueError("Use even output dimensions and 1–60 FPS.")


def centered_crop(width, height, ratio, within=Crop()):
    """Largest centered rectangle with a pixel aspect ratio inside a crop."""
    x, y, w, h = within.pixels(width, height)
    if w / h > ratio:
        new_w = h * ratio
        x += (w - new_w) / 2
        w = new_w
    else:
        new_h = w / ratio
        y += (h - new_h) / 2
        h = new_h
    return Crop(x / width, y / height, w / width, h / height)


def content_rect(widget_width, widget_height, frame_width, frame_height):
    scale = min(widget_width / frame_width, widget_height / frame_height)
    w, h = frame_width * scale, frame_height * scale
    return (widget_width - w) / 2, (widget_height - h) / 2, w, h


def drag_crop(start, end, rectangle):
    x, y, w, h = rectangle
    points = [(max(0, min(1, (px - x) / w)), max(0, min(1, (py - y) / h)))
              for px, py in (start, end)]
    left, right = sorted(p[0] for p in points)
    top, bottom = sorted(p[1] for p in points)
    if right - left < 0.005 or bottom - top < 0.005:
        return None
    return Crop(left, top, right - left, bottom - top)


class Presets:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kagami/receiver-presets.json"

    def _read(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text())
        if not isinstance(data, dict):
            raise ValueError("Invalid receiver preset file.")
        return data

    @staticmethod
    def key(serial, app, frame):
        # Dimensions identify captured orientation; no frame or app data is stored.
        return json.dumps([serial, app, frame.width, frame.height], ensure_ascii=False)

    def load(self, serial, app, frame, default=Framing()):
        value = self._read().get(self.key(serial, app, frame))
        return Framing(crop=Crop(**value["crop"]), rotation=value["rotation"],
                       mirror=value["mirror"], fit=value["fit"]) if value else default

    def save(self, serial, app, frame, framing):
        data = self._read()
        data[self.key(serial, app, frame)] = asdict(framing)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        temporary.chmod(0o600)
        temporary.replace(self.path)
