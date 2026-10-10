"""Last explicit desktop choices, separate from device/orientation presets."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile

from .model import Crop, Framing, OutputConfig
from .smartview import interface_name

TRANSPORTS = ("smartview", "airplay", "usb", "wifi")


@dataclass(frozen=True)
class DesktopPreferences:
    output: OutputConfig = OutputConfig()
    interface: str = "wlo1"
    transport: str = "smartview"
    framing: Framing = Framing()
    aspect: int = 0
    label: str = "Samsung Camera"

    def __post_init__(self):
        interface_name(self.interface)
        if self.transport not in TRANSPORTS:
            raise ValueError("Unknown preferred transport.")
        if type(self.aspect) is not int or not 0 <= self.aspect <= 4:
            raise ValueError("Unknown crop aspect ratio.")
        if not isinstance(self.label, str) or len(self.label) > 200:
            raise ValueError("Preset label must be at most 200 characters.")


class Settings:
    def __init__(self, path=None):
        default = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kagami/settings.json"
        self.path = Path(path or os.environ.get("KAGAMI_SETTINGS_FILE") or default)

    def _read(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid receiver settings file.")
        return data

    def load(self, defaults=DesktopPreferences()):
        data = self._read()
        output = defaults.output
        output = OutputConfig(data.get("source", output.source), data.get("output", output.device),
                              data.get("width", output.width), data.get("height", output.height), data.get("fps", output.fps))
        value = data.get("framing", asdict(defaults.framing))
        if (not isinstance(value, dict) or type(value.get("mirror")) is not bool
                or type(value.get("rotation")) is not int):
            raise ValueError("Invalid saved framing.")
        framing = Framing(Crop(**value["crop"]), value["rotation"], value["mirror"], value["fit"])
        return DesktopPreferences(output, data.get("interface", defaults.interface),
                                  data.get("preferred_transport", defaults.transport), framing,
                                  data.get("crop_aspect", defaults.aspect), data.get("preset_label", defaults.label))

    def save(self, preferences):
        # Merge installer metadata/unknown future keys; never replace presets.
        data = self._read()
        output = preferences.output
        data.update(source=output.source, output=output.device, width=output.width, height=output.height,
                    fps=output.fps, interface=preferences.interface, preferred_transport=preferences.transport,
                    framing=asdict(preferences.framing), crop_aspect=preferences.aspect, preset_label=preferences.label)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".settings-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
