#!/usr/bin/env python3
"""Preserved V2 installation settings, safe node selection and user launchers."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/receiver"), str(ROOT / "apps/host")]
from kagami_receiver.model import OutputConfig
from kagami_receiver.smartview import interface_modes, interface_name
from install_launchers import desktop_quote


def camera_numbers(settings=None, *, devices=Path("/dev"), names=Path("/sys/class/video4linux")):
    """Reuse identified nodes; select free slots without touching any device."""
    chosen = []
    for key, label in (("output", "Kagami Virtual Camera"), ("source", "Kagami Screen Input")):
        if settings:
            number = int(settings[key].removeprefix("/dev/video"))
        else:
            matches = sorted(int(p.parent.name.removeprefix("video")) for p in names.glob("video*/name")
                             if p.read_text().strip() == label)
            number = next((n for n in matches if n not in chosen), None)
            if number is None:
                number = next((n for n in range(10, 64) if n not in chosen and
                               not (devices / f"video{n}").exists() and not (devices / f"video{n}").is_symlink()), None)
            if number is None:
                raise ValueError("No free Kagami camera slot between video10 and video63.")
        node = devices / f"video{number}"
        if node.exists() or node.is_symlink():
            name = names / f"video{number}/name"
            if not name.is_file() or name.read_text().strip() != label:
                raise ValueError(f"Camera slot video{number} is occupied; leaving it untouched.")
        if number in chosen:
            raise ValueError("Input and output must use different camera slots.")
        chosen.append(number)
    return chosen


def wireless_interface():
    candidates = []
    for device in sorted(Path("/sys/class/net").iterdir()):
        if not (device / "phy80211").exists():
            continue
        candidates.append(device.name)
        try:
            phy = (device / "phy80211").resolve().name
            info = subprocess.run(["iw", "phy", phy, "info"], check=True, capture_output=True, text=True, timeout=5)
            if {"P2P-client", "P2P-GO"}.issubset(interface_modes(info.stdout)):
                return device.name
        except (OSError, subprocess.SubprocessError):
            pass
    return candidates[0] if candidates else "wlo1"


def prepare(path, selected_interface=None, **camera_paths):
    path = Path(path)
    settings = json.loads(path.read_text()) if path.exists() else None
    if settings is not None:
        OutputConfig(settings["source"], settings["output"], settings["width"], settings["height"], settings["fps"])
    output, source = camera_numbers(settings, **camera_paths)
    interface = interface_name(selected_interface or (settings or {}).get("interface") or wireless_interface())
    if settings is None:
        settings = {"source": f"/dev/video{source}", "output": f"/dev/video{output}",
                    "width": 1280, "height": 720, "fps": 30, "interface": interface}
    elif selected_interface:
        settings["interface"] = interface
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".next")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    return settings


def write_launchers(root, config, data, *, home=None):
    root, config, data = (Path(p).absolute() for p in (root, config, data))
    home = Path(home) if home else Path.home()
    settings = json.loads(config.read_text())
    OutputConfig(settings["source"], settings["output"], settings["width"], settings["height"], settings["fps"])
    interface_name(settings["interface"])
    launcher = home / ".local/bin/kagami"
    desktop = data / "applications/io.kagami.Host.desktop"
    command = desktop_quote(launcher)
    args = ["--source", settings["source"], "--output", settings["output"],
            "--width", str(settings["width"]), "--height", str(settings["height"]),
            "--fps", str(settings["fps"]), "--interface", settings["interface"]]
    launcher.parent.mkdir(parents=True, exist_ok=True)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("#!/bin/sh\nset -eu\n"
                        'if [ "$(id -u)" = 0 ]; then echo "Run Kagami as your desktop user." >&2; exit 2; fi\n'
                        "export KAGAMI_PYTHON=/usr/bin/python3\n"
                        f"exec /bin/sh {shlex.quote(str(root / 'current/tools/run-receiver.sh'))} "
                        + shlex.join(args) + ' "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    desktop.write_text("[Desktop Entry]\nType=Application\nName=Kagami\n"
                       "Comment=Phone screen to virtual camera\n"
                       f"Exec={command}\nIcon=camera-video\nTerminal=false\n"
                       "Categories=AudioVideo;Video;\nStartupNotify=true\n", encoding="utf-8")
    return launcher, desktop


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "launchers", "check"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--interface")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(args.config, args.interface)))
    elif args.action == "launchers":
        if not args.root or not args.data:
            parser.error("launchers requires --root and --data")
        write_launchers(args.root, args.config, args.data)
    else:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_foreign("cairo")
        from gi.repository import Gtk
        from kagami_receiver.smartview import preflight
        settings = json.loads(args.config.read_text())
        checks = preflight(settings["interface"])
        checks.append({"name": "gtk4", "ok": (Gtk.get_major_version(), Gtk.get_minor_version()) >= (4, 8), "detail": "GTK4 + Cairo"})
        print(json.dumps({"checks": checks, "samsung_interoperability": "physical Galaxy test pending"}))
        sys.exit(2 if any(not c["ok"] for c in checks if c["name"] != "wifi_direct") else
                 10 if any(not c["ok"] for c in checks) else 0)
