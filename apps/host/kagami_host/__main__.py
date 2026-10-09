"""Run with PYTHONPATH=apps/host python3 -m kagami_host [serve|doctor]."""

import argparse
import asyncio
import json
from pathlib import Path
import signal
import sys

from .config import load_config


def report(message):
    print(json.dumps(message, ensure_ascii=False), flush=True)


async def serve(config):
    from aiohttp import web
    from .media import GstReceiver
    from .server import create_app, STATE_KEY, tls_context

    tls = tls_context(config)
    backend = GstReceiver(config, lambda _event: None)
    runner = None
    try:
        await backend.start()
        app = create_app(config, backend, report)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=5)
        await runner.setup()
        site = web.TCPSite(runner, host=config.host, port=config.port, ssl_context=tls)
        await site.start()
        state = app[STATE_KEY]
        report({"event": "ready", "pair_url": f"{config.origin}/#pair={state.pairing.token}",
                "pairing_seconds": 300, "device": config.device, "output": config.output})
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        for value in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(value, stopped.set)
        await stopped.wait()
    finally:
        if runner:
            await runner.cleanup()
        else:
            await backend.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Kagami local HTTPS/WebRTC → V4L2 reference host")
    parser.add_argument("action", choices=("serve", "doctor"), nargs="?", default="serve")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.action == "doctor":
            from .doctor import checks
            results = checks(config)
            report({"event": "doctor", "checks": results})
            return 0 if all(result["ok"] for result in results) else 2
        asyncio.run(serve(config))
    except (OSError, ValueError, RuntimeError, ImportError, asyncio.TimeoutError) as exc:
        report({"event": "error", "message": str(exc)})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
