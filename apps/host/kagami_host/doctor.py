"""Read-only environment checks. No module loading or privilege escalation."""

import importlib.util
from pathlib import Path
import shutil

from .v4l2 import query_device


def checks(config):
    results = []

    def add(name, ok, message):
        results.append({"check": name, "ok": bool(ok), "message": message})

    gi = importlib.util.find_spec("gi") is not None
    add("python_gi", gi, "Available" if gi else "Install python3-gobject and use Fedora's system Python.")
    add("aiohttp", importlib.util.find_spec("aiohttp") is not None, "Host requires aiohttp.")
    add("gst_inspect", shutil.which("gst-inspect-1.0"), "Install GStreamer tools/plugins; see docs/fedora-setup.md.")
    if gi:
        try:
            from .media import gst_modules
            _glib, gst, _sdp, _webrtc = gst_modules()
            add("gstreamer_plugins", True, gst.version_string())
        except RuntimeError as exc:
            add("gstreamer_plugins", False, str(exc))
    for name, path in (("tls_certificate", config.certificate), ("tls_private_key", config.private_key)):
        add(name, path.is_file(), str(path))
    try:
        from .server import tls_context
        tls_context(config)
        add("tls_key_match", True, "Certificate/key loaded. Phone trust still requires the documented bootstrap.")
    except (OSError, ValueError) as exc:
        add("tls_key_match", False, str(exc))
    add("loopback_module", Path("/sys/module/v4l2loopback").exists(), "Use the documented one-time driver setup.")
    try:
        info = query_device(config.device)
        add("virtual_device", True, info["card"])
    except (OSError, ValueError) as exc:
        add("virtual_device", False, str(exc))
    return results
