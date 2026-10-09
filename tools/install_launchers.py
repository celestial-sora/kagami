#!/usr/bin/env python3
"""Write user-owned launchers with shell/Desktop Entry escaping for real paths."""
import argparse
import os
from pathlib import Path
import shlex


def desktop_quote(value):
    value = str(value)
    if any(char in value for char in ("\n", "\r", "\0")):
        raise ValueError("Launcher paths cannot contain control characters.")
    # Desktop Entry string escaping is applied after Exec argument quoting.
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"' + value.replace("\\", "\\\\").replace("%", "%%") + '"'


def write_launchers(root, config, data, home=None):
    root, config, data = (Path(value).absolute() for value in (root, config, data))
    home = Path(home) if home else Path.home()
    launcher = home / ".local/bin/kagami"
    desktop = data / "applications/io.kagami.Host.desktop"
    # Validate before writing either file.
    command = desktop_quote(launcher)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("#!/bin/sh\nset -eu\n"
                        'if [ "$(id -u)" = 0 ]; then echo "Run Kagami as your desktop user." >&2; exit 2; fi\n'
                        f"export KAGAMI_ROOT={shlex.quote(str(root / 'current'))}\n"
                        f"export KAGAMI_CONFIG={shlex.quote(str(config))}\n"
                        "export KAGAMI_PYTHON=/usr/bin/python3\n"
                        f"exec {shlex.quote(str(root / 'current/bin/kagami-linux'))} \"$@\"\n", encoding="utf-8")
    os.chmod(launcher, 0o755)
    desktop.write_text("[Desktop Entry]\nType=Application\nName=Kagami\n"
                       "Comment=Local phone camera for Linux\n"
                       f"Exec={command}\nIcon=camera-video\nTerminal=false\n"
                       "Categories=AudioVideo;Video;\nStartupNotify=true\n", encoding="utf-8")
    return launcher, desktop


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("root", "config", "data"):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args()
    write_launchers(args.root, args.config, args.data)
