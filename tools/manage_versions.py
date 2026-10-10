#!/usr/bin/env python3
"""Switch preserved application versions without downloading or running as root."""
import argparse
import os
from pathlib import Path
import re
import uuid


def version_path(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    if target.parent != root / "versions" or not target.name.startswith("v2-"):
        raise ValueError("Choose an installed V2 version inside Kagami's versions directory.")
    sha = (target / "VERSION").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not (target / "tools/run-receiver.sh").is_file():
        raise ValueError("The installed version is incomplete.")
    return target


def replace_link(path, target):
    temporary = path.with_name(path.name + ".next." + uuid.uuid4().hex)
    try:
        temporary.symlink_to(target)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def activate(root, target):
    root = Path(root).resolve()
    target = version_path(root, target)
    current = root / "current"
    if current.is_symlink() and current.resolve() != target:
        # Preserve even an archival V1 directory; rollback only accepts V2.
        replace_link(root / "previous", current.resolve())
    replace_link(current, target)
    return target


def rollback(root):
    root = Path(root).resolve()
    previous = root / "previous"
    if not previous.is_symlink():
        raise ValueError("No previous application version is available.")
    return activate(root, previous.resolve())


def versions(root):
    root = Path(root).resolve()
    for path in sorted((root / "versions").glob("v2-*")):
        try:
            target = version_path(root, path)
        except (OSError, ValueError):
            continue
        markers = [label for label in ("current", "previous") if (root / label).resolve() == target]
        yield path.name + (" [" + ", ".join(markers) + "]" if markers else "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("action", choices=("activate", "rollback", "versions"))
    parser.add_argument("target", nargs="?", type=Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.exit(2, "Run Kagami as your desktop user.\n")
    try:
        if args.action == "activate":
            if not args.target:
                parser.error("activate requires an installed version path")
            print("Activated " + str(activate(args.root, args.target)))
        elif args.action == "rollback":
            print("Rolled back application to " + str(rollback(args.root)))
            print("Restart Kagami. Shared system packages/backends are unchanged.")
        else:
            print("\n".join(versions(args.root)) or "No installed V2 versions.")
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
