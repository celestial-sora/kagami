"""A deliberately small, explicit configuration for one local IPv4 interface."""

from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    device: str
    certificate: Path
    private_key: Path
    width: int = 1280
    height: int = 720
    fps: int = 30
    udp_port_min: int = 50000
    udp_port_max: int = 50100

    @property
    def origin(self) -> str:
        return f"https://{self.host}:{self.port}"

    @property
    def output(self) -> dict:
        return {"width": self.width, "height": self.height, "fps": self.fps,
                "format": "YUY2", "codec": "VP8"}


def load_config(path: Path) -> Config:
    path = path.resolve()
    values = json.loads(path.read_text(encoding="utf-8"))
    allowed = {"host", "port", "device", "certificate", "private_key", "width", "height", "fps", "udp_port_min", "udp_port_max"}
    if not isinstance(values, dict) or set(values) - allowed:
        raise ValueError("Configuration must be an object with documented fields only.")
    host = values.get("host", "127.0.0.1")
    if not isinstance(host, str):
        raise ValueError("host must be a local IPv4 string.")
    address = ipaddress.IPv4Address(host)
    if address.is_unspecified or address.is_multicast or not (address.is_private or address.is_loopback):
        raise ValueError("Choose a reachable local IPv4 address, not a wildcard or public IP.")
    port = values.get("port", 8443)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be an integer between 1 and 65535.")
    device = values.get("device", "/dev/video10")
    if not isinstance(device, str) or not re.fullmatch(r"/dev/video[0-9]+", device):
        raise ValueError("device must be an explicit /dev/videoN device.")
    width, height, fps = (values.get("width", 1280), values.get("height", 720), values.get("fps", 30))
    if any(type(v) is not int for v in (width, height, fps)) or (width, height) not in ((1280, 720), (1920, 1080)) or fps not in (15, 30):
        raise ValueError("Use 1280x720 or 1920x1080, with 15 or 30 FPS.")
    paths = []
    udp_min, udp_max = values.get("udp_port_min", 50000), values.get("udp_port_max", 50100)
    if any(type(v) is not int for v in (udp_min, udp_max)) or not 1024 <= udp_min <= udp_max <= 65535:
        raise ValueError("ICE UDP ports must form an ordered range between 1024 and 65535.")
    for field in ("certificate", "private_key"):
        value = values.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must name a TLS file.")
        paths.append((path.parent / value).resolve())
    return Config(str(address), port, device, *paths, width, height, fps, udp_min, udp_max)
