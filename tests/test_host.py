"""Real TLS/HTTP/WebSocket tests with an explicit recording media test double.

These tests verify auth, signaling and teardown; they do NOT claim GStreamer,
Android, Fedora, a kernel module, or OBS hardware validation.
"""

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/host"), str(ROOT / "tools")]

from aiohttp import ClientSession, CookieJar, TCPConnector, WSServerHandshakeError, WSMsgType, web
from create_tls import create_tls
from kagami_host.config import Config, load_config
from kagami_host.protocol import validate_signal
from kagami_host.server import COOKIE, STATE_KEY, create_app, tls_context
from kagami_host.session import Pairing, PairingLimiter


class SessionTests(unittest.TestCase):
    def test_expiry_replay_and_revocation(self):
        now = [0.0]
        pairing = Pairing(clock=lambda: now[0], pairing_ttl=5, session_ttl=10)
        token = pairing.token
        self.assertIsNone(pairing.exchange("incorrect"))
        session = pairing.exchange(token)
        self.assertTrue(pairing.authorized(session))
        self.assertIsNone(pairing.exchange(token))
        self.assertFalse(pairing.authorized("wrong-session"))
        now[0] = 10
        self.assertFalse(pairing.authorized(session))
        pairing.revoke()
        self.assertFalse(pairing.authorized(session))

    def test_unused_pairing_token_expires_at_deadline(self):
        now = [0.0]
        pairing = Pairing(clock=lambda: now[0], pairing_ttl=5)
        now[0] = 5
        self.assertIsNone(pairing.exchange(pairing.token))

    def test_pairing_rate_limit_recovers_and_memory_is_bounded(self):
        now = [0.0]
        limiter = PairingLimiter(clock=lambda: now[0])
        for _ in range(10):
            self.assertTrue(limiter.allow("phone"))
        self.assertFalse(limiter.allow("phone"))
        now[0] = 60
        self.assertTrue(limiter.allow("phone"))
        for number in range(1100):
            limiter.allow(str(number))
        self.assertLessEqual(len(limiter.attempts), 1024)

    def test_protocol_rejects_audio_multiple_tracks_and_invalid_versions(self):
        for message in ({"v": True, "type": "offer", "sdp": "v=0"},
                        {"v": 2, "type": "offer", "sdp": "v=0"},
                        {"v": 1, "type": "offer", "sdp": "v=0\r\nm=audio 9 RTP/AVP 0\r\n"},
                        {"v": 1, "type": "offer", "sdp": "v=0\r\nm=video 9 RTP/AVP 96\r\nm=video 9 RTP/AVP 96\r\n"},
                        {"v": 1, "type": "ice", "candidate": {"candidate": "candidate:x\nmalformed", "sdpMLineIndex": 0}}):
            with self.subTest(message=message), self.assertRaises(ValueError):
                validate_signal(message)

    def test_config_rejects_public_wildcard_and_arbitrary_device(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            base = json.loads((ROOT / "config.example.json").read_text())
            for update in ({"host": "0.0.0.0"}, {"host": "8.8.8.8"}, {"device": "/tmp/output"},
                           {"fps": True}, {"port": "8443"}, {"width": 4},
                           {"udp_port_min": 50101, "udp_port_max": 50100},
                           {"udp_port_min": True}, {"udp_port_max": 70000}):
                path.write_text(json.dumps({**base, **update}))
                with self.subTest(update=update), self.assertRaises(ValueError):
                    load_config(path)
            path.write_text(json.dumps(base))
            config = load_config(path)
            self.assertEqual(config.certificate, Path(directory) / ".local/tls/server.pem")


class RecordingMedia:
    def __init__(self):
        self.emit = lambda _message: None
        self.begins = 0
        self.offers = []
        self.candidates = []
        self.stopped = asyncio.Event()
        self.closed = False

    async def begin_session(self):
        self.stopped.clear()
        self.begins += 1

    async def offer(self, sdp):
        self.offers.append(sdp)
        self.emit({"v": 1, "type": "answer", "sdp": "recording-test-double-answer"})

    async def ice(self, candidate):
        self.candidates.append(candidate)

    async def stop_stream(self):
        self.stopped.set()

    def metrics(self):
        return {"state": "waiting", "incoming_fps": 0, "output_fps": 0}

    async def shutdown(self):
        self.closed = True


class HttpsHostTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.tls = create_tls(Path(cls.directory.name) / "tls", ["127.0.0.1"])

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    async def asyncSetUp(self):
        config = Config("127.0.0.1", 8443, "/dev/video10", self.tls / "server.pem", self.tls / "server.key")
        self.backend = RecordingMedia()
        self.reports = []
        self.app = create_app(config, self.backend, self.reports.append)
        self.state = self.app[STATE_KEY]
        self.runner = web.AppRunner(self.app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0, ssl_context=tls_context(config))
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.origin = f"https://127.0.0.1:{port}"
        self.state.origin = self.origin
        context = ssl.create_default_context(cafile=str(self.tls / "ca.pem"))
        self.client = ClientSession(connector=TCPConnector(ssl=context), cookie_jar=CookieJar(unsafe=True))

    async def asyncTearDown(self):
        await self.client.close()
        await self.runner.cleanup()
        self.assertTrue(self.backend.closed)

    async def pair(self):
        return await self.client.post(self.origin + "/api/pair", headers={"Origin": self.origin},
                                      json={"v": 1, "token": self.state.pairing.token})

    async def connect(self):
        return await self.client.ws_connect(self.origin + "/signal", headers={"Origin": self.origin})

    async def test_tls_pairing_has_private_cookie_and_rejects_replay(self):
        token = self.state.pairing.token
        response = await self.pair()
        self.assertEqual(response.status, 200)
        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertNotIn(token, await response.text())
        replay = await self.client.post(self.origin + "/api/pair", headers={"Origin": self.origin}, json={"v": 1, "token": token})
        self.assertEqual(replay.status, 401)
        status = await self.client.get(self.origin + "/api/state")
        self.assertEqual(status.status, 200)
        self.assertEqual(status.headers["Cache-Control"], "no-store")
        self.assertNotIn(token, json.dumps(self.reports))

    async def test_default_trust_store_does_not_accept_the_local_ca(self):
        async with ClientSession() as untrusted:
            from aiohttp import ClientConnectorCertificateError
            with self.assertRaises(ClientConnectorCertificateError):
                await untrusted.get(self.origin + "/")

    async def test_wrong_origin_missing_origin_and_wrong_token_are_rejected(self):
        for origin in (None, "https://evil.example"):
            headers = {"Origin": origin} if origin else {}
            response = await self.client.post(self.origin + "/api/pair", headers=headers,
                                              json={"v": 1, "token": self.state.pairing.token})
            self.assertEqual(response.status, 403)
        response = await self.client.post(self.origin + "/api/pair", headers={"Origin": self.origin}, json={"v": 1, "token": "wrong"})
        self.assertEqual(response.status, 401)
        response = await self.client.get(self.origin + "/api/state")
        self.assertEqual(response.status, 401)
        with self.assertRaises(WSServerHandshakeError) as error:
            await self.connect()
        self.assertEqual(error.exception.status, 401)

    async def test_cross_origin_websocket_rejected_after_pairing(self):
        await self.pair()
        with self.assertRaises(WSServerHandshakeError) as error:
            await self.client.ws_connect(self.origin + "/signal", headers={"Origin": "https://evil.example"})
        self.assertEqual(error.exception.status, 403)

    async def test_offer_ice_and_reconnect_flow(self):
        await self.pair()
        socket = await self.connect()
        self.assertEqual((await socket.receive_json())["type"], "ready")
        sdp = "v=0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
        await socket.send_json({"v": 1, "type": "offer", "sdp": sdp})
        self.assertEqual((await socket.receive_json())["type"], "answer")
        candidate = {"candidate": "candidate:1 1 UDP 1 127.0.0.1 5000 typ host", "sdpMLineIndex": 0}
        await socket.send_json({"v": 1, "type": "ice", "candidate": candidate})
        await socket.close()
        await asyncio.wait_for(self.backend.stopped.wait(), 2)
        self.assertEqual(self.backend.offers, [sdp])
        self.assertEqual(self.backend.candidates, [candidate])
        again = await self.connect()
        self.assertEqual((await again.receive_json())["type"], "ready")
        self.assertEqual(self.backend.begins, 2)
        await again.close()

    async def test_second_sender_is_rejected(self):
        await self.pair()
        first = await self.connect()
        await first.receive_json()
        with self.assertRaises(WSServerHandshakeError) as error:
            await self.connect()
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.backend.begins, 1)
        await first.close()

    async def test_invalid_message_stops_media_and_allows_retry(self):
        await self.pair()
        socket = await self.connect()
        await socket.receive_json()
        await socket.send_json({"v": 99, "type": "offer", "sdp": "v=0"})
        self.assertEqual((await socket.receive_json())["type"], "error")
        await socket.close()
        await asyncio.wait_for(self.backend.stopped.wait(), 2)
        again = await self.connect()
        await again.receive_json()
        await again.close()

    async def test_session_expiry_closes_existing_stream(self):
        await self.pair()
        socket = await self.connect()
        await socket.receive_json()
        self.state.pairing.session_expires_at = time.monotonic() - 1
        event = await asyncio.wait_for(socket.receive(), 3)
        self.assertEqual(event.type, WSMsgType.CLOSE)
        self.assertEqual(event.data, 1008)
        await socket.close()

    async def test_only_client_assets_are_served(self):
        for path in ("/config.json", "/.local/tls/server.key", "/ca.key", "/docs/security.md"):
            async with self.client.get(self.origin + path) as response:
                self.assertEqual(response.status, 404)
                await response.read()
        async with self.client.get(self.origin + "/") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            await response.read()

    async def test_certificate_generation_preserves_existing_identity(self):
        before = (self.tls / "ca.pem").read_bytes()
        with self.assertRaises(ValueError):
            create_tls(self.tls, ["127.0.0.1"])
        self.assertEqual((self.tls / "ca.pem").read_bytes(), before)
        self.assertEqual(os.stat(self.tls / "ca.key").st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
