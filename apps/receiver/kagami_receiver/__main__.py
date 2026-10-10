"""Kagami V2: native GTK desktop or headless receiver/diagnostics."""

import argparse
from dataclasses import asdict
import getpass
import json
import os
import signal
import sys
import time

from .model import Framing, OutputConfig, ReceiverError
from .transport import ScrcpyTransport, connect, devices, pair, scrcpy_capabilities


def report(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("desktop", "doctor", "devices", "pair", "connect", "mirror", "smartview", "smartview-doctor"), default="desktop")
    parser.add_argument("--source", default="/dev/video11")
    parser.add_argument("--output", default="/dev/video10")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--serial")
    parser.add_argument("--mode", choices=("usb", "wifi"), default="usb")
    parser.add_argument("--endpoint")
    parser.add_argument("--crop", help="Normalized x,y,width,height")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--fit", choices=("fit", "fill"), default="fit")
    parser.add_argument("--interface", default="wlo1")
    parser.add_argument("--allow-network-disconnect", action="store_true")
    args = parser.parse_args()
    receiver = None
    cleanup_failed = False
    try:
        if os.geteuid() == 0:
            raise ReceiverError("permission", "Run Kagami as your desktop user, never as root.")
        config = OutputConfig(args.source, args.output, args.width, args.height, args.fps)
        if args.action == "devices":
            report({"devices": [asdict(item) for item in devices()]})
        elif args.action in ("pair", "connect"):
            if not args.endpoint:
                parser.error("--endpoint IP:port is required")
            report({"message": pair(args.endpoint, getpass.getpass("Android pairing code: ")) if args.action == "pair" else connect(args.endpoint)})
        elif args.action == "smartview-doctor":
            from .smartview import preflight
            checks = preflight(args.interface)
            report({"checks": checks, "samsung_interoperability": "physical Galaxy test pending"})
            return 0 if all(c["ok"] for c in checks) else 2
        elif args.action == "doctor":
            from kagami_host.v4l2 import query_device
            from .pipeline import gst
            checks = []
            for name, function in (("scrcpy", scrcpy_capabilities), ("adb", lambda: [asdict(d) for d in devices()]),
                                   ("gstreamer", lambda: gst().version_string()),
                                   ("input_loopback", lambda: query_device(config.source)),
                                   ("output_loopback", lambda: query_device(config.device))):
                try:
                    checks.append({"name": name, "ok": True, "detail": function()})
                except (ValueError, RuntimeError, OSError) as exc:
                    checks.append({"name": name, "ok": False, "detail": str(exc)})
            report({"checks": checks, "consumer_test": "pending manual OBS and second V4L2 consumer verification"})
            return 0 if all(c["ok"] for c in checks) else 2
        elif args.action == "desktop":
            from .desktop import run
            return run(config)
        else:
            from .controller import Receiver
            from .model import Crop
            if args.action != "smartview" and not args.serial:
                parser.error("mirror requires --serial from the devices command")
            identity = next((d for d in devices() if d.serial == args.serial), None) if args.action != "smartview" else None
            if args.action != "smartview" and identity is None:
                raise ReceiverError("connectivity", "Selected Android device is not connected.")
            receiver = Receiver(config)
            crop = Crop(*map(float, args.crop.split(","))) if args.crop else Crop()
            receiver.framing = Framing(crop, args.rotation, args.mirror, args.fit)
            stopped = False
            def stop(_signal, _frame):
                nonlocal stopped
                stopped = True
            for value in (signal.SIGTERM, signal.SIGINT):
                signal.signal(value, stop)
            if args.action == "smartview":
                from .smartview import SmartViewTransport
                adapter = SmartViewTransport(args.interface, allow_disconnect=args.allow_network_disconnect)
            else:
                adapter = ScrcpyTransport(identity, args.mode)
            receiver.start(adapter)
            next_report = 0
            while not stopped:
                receiver.tick()
                if receiver.state == "disconnected":
                    raise ReceiverError("connectivity", receiver.error_message)
                if time.monotonic() >= next_report:
                    report(receiver.metrics())
                    next_report = time.monotonic() + 1
                time.sleep(.1)
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        report({"error": str(exc), "category": getattr(exc, "category", "format")})
        return 2
    finally:
        if receiver:
            try:
                receiver.stop()
            except (OSError, RuntimeError) as exc:
                report({"error": str(exc), "category": "connectivity"})
                cleanup_failed = True
    return 2 if cleanup_failed else 0


if __name__ == "__main__":
    sys.exit(main())
