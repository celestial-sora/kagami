"""HTTPS-only single-phone signaling. No public relays and no media URL output."""

import asyncio
from contextlib import suppress
import json
from pathlib import Path
import ssl

from aiohttp import web, WSMsgType

from .protocol import validate_signal
from .session import Pairing, PairingLimiter

COOKIE = "kagami_session"
CLIENT_ROOT = Path(__file__).resolve().parents[2] / "web-client"
STATE_KEY = web.AppKey("kagami_state", object)


class HostState:
    def __init__(self, config, backend, report):
        self.config, self.backend, self.report = config, backend, report
        self.origin = config.origin
        self.pairing = Pairing()
        self.limiter = PairingLimiter()
        self.socket = None
        self.socket_session = None
        self.events = None
        self.lock = asyncio.Lock()
        self.metrics = {"state": "waiting"}

    def media_event(self, message):
        if self.events is not None:
            try:
                self.events.put_nowait(message)
            except asyncio.QueueFull:
                if self.socket:
                    asyncio.create_task(self.socket.close(code=1011, message=b"Signaling queue overflow"))


def json_response(data, status=200):
    return web.json_response(data, status=status)


@web.middleware
async def headers(request, handler):
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
    response.headers.update({
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Permissions-Policy": "camera=(self), microphone=(), display-capture=()",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    })
    if isinstance(response, web.HTTPException):
        raise response
    return response


def same_origin(request, state):
    return request.headers.get("Origin") == state.origin


def authorized(request, state):
    return state.pairing.authorized(request.cookies.get(COOKIE))


async def pair(request):
    state = request.app[STATE_KEY]
    if not same_origin(request, state):
        return json_response({"error": "origin_rejected"}, 403)
    if not state.limiter.allow(request.remote):
        return json_response({"error": "too_many_attempts"}, 429)
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError):
        return json_response({"error": "invalid_json"}, 400)
    if not isinstance(data, dict) or type(data.get("v")) is not int or data["v"] != 1:
        return json_response({"error": "protocol_mismatch"}, 400)
    session = state.pairing.exchange(data.get("token"))
    if not session:
        return json_response({"error": "pairing_expired_or_used", "message": "Restart the host to obtain a fresh QR code."}, 401)
    response = json_response({"v": 1, "paired": True, "output": state.config.output})
    response.set_cookie(COOKIE, session, max_age=28800, secure=True, httponly=True, samesite="Strict", path="/")
    state.report({"event": "paired"})
    return response


async def status(request):
    state = request.app[STATE_KEY]
    if not authorized(request, state):
        return json_response({"error": "not_paired"}, 401)
    return json_response({"v": 1, "paired": True, "output": state.config.output,
                          "streaming": state.socket is not None, "metrics": state.metrics})


async def send_events(state, socket, events):
    while True:
        message = await events.get()
        await socket.send_json(message)
        if message.get("type") == "error":
            await socket.close(code=1011)
            return


async def signaling(request):
    state = request.app[STATE_KEY]
    if not same_origin(request, state):
        return json_response({"error": "origin_rejected"}, 403)
    if not authorized(request, state):
        return json_response({"error": "not_paired"}, 401)
    async with state.lock:
        if state.socket is not None:
            return json_response({"error": "phone_already_connected"}, 409)
        socket = web.WebSocketResponse(max_msg_size=131072, heartbeat=15)
        state.socket = socket
        state.socket_session = request.cookies.get(COOKIE)
        state.events = asyncio.Queue(maxsize=64)
    events = state.events
    consumer = None
    try:
        await socket.prepare(request)
        await state.backend.begin_session()
        consumer = asyncio.create_task(send_events(state, socket, events))
        await socket.send_json({"v": 1, "type": "ready", "output": state.config.output})
        offered = False
        async for item in socket:
            if not authorized(request, state):
                await socket.close(code=1008, message=b"Session expired")
                break
            if item.type != WSMsgType.TEXT:
                if item.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
                await socket.close(code=1003, message=b"Text messages required")
                break
            try:
                message = validate_signal(json.loads(item.data))
                if message["type"] == "offer":
                    if offered:
                        raise ValueError("Open a new connection to renegotiate video.")
                    offered = True
                    await state.backend.offer(message["sdp"])
                else:
                    await state.backend.ice(message["candidate"])
            except (ValueError, TypeError, KeyError) as exc:
                await socket.send_json({"v": 1, "type": "error", "message": str(exc)})
                await socket.close(code=1008)
                break
    except (RuntimeError, OSError, asyncio.TimeoutError) as exc:
        state.report({"event": "error", "message": str(exc)})
        if socket.prepared and not socket.closed:
            await socket.send_json({"v": 1, "type": "error", "message": "Media receiver failed. Check the Linux host."})
            await socket.close(code=1011)
    finally:
        if consumer:
            consumer.cancel()
            with suppress(asyncio.CancelledError, ConnectionResetError):
                await consumer
        # Hold the slot until the old receiver is stopped; a new session cannot
        # race its predecessor's teardown and accidentally stop the new stream.
        try:
            await state.backend.stop_stream()
        finally:
            async with state.lock:
                state.socket = state.events = None
                state.socket_session = None
        state.report({"event": "disconnected"})
    return socket


async def static_file(request):
    names = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
    name = names.get(request.path)
    if name is None:
        raise web.HTTPNotFound()
    return web.FileResponse(CLIENT_ROOT / name)


async def monitor(state):
    while True:
        await asyncio.sleep(1)
        state.metrics = state.backend.metrics()
        state.report({"event": "metrics", **state.metrics})
        if state.socket:
            if not state.pairing.authorized(state.socket_session):
                await state.socket.close(code=1008, message=b"Session expired")
            else:
                state.media_event({"v": 1, "type": "status", **state.metrics})


def create_app(config, backend, report=lambda _event: None):
    state = HostState(config, backend, report)
    backend.emit = state.media_event
    app = web.Application(client_max_size=131072, middlewares=[headers])
    app[STATE_KEY] = state
    app.router.add_post("/api/pair", pair)
    app.router.add_get("/api/state", status)
    app.router.add_get("/signal", signaling)
    for path in ("/", "/app.js", "/styles.css"):
        app.router.add_get(path, static_file)

    async def startup(_app):
        state.monitor = asyncio.create_task(monitor(state))

    async def shutdown(_app):
        state.pairing.revoke()
        state.monitor.cancel()
        with suppress(asyncio.CancelledError):
            await state.monitor
        if state.socket:
            await state.socket.close(code=1001, message=b"Host stopped")

    async def cleanup(_app):
        await backend.shutdown()

    app.on_startup.append(startup)
    app.on_shutdown.append(shutdown)
    app.on_cleanup.append(cleanup)
    return app


def tls_context(config):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config.certificate, config.private_key)
    return context
