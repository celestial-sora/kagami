"""One-time, expiring pairing and one authorized streaming session."""

from collections import OrderedDict, deque
import secrets
import time


class Pairing:
    def __init__(self, clock=time.monotonic, pairing_ttl=300, session_ttl=28800):
        self.clock = clock
        self.token = secrets.token_urlsafe(32)
        self.expires_at = clock() + pairing_ttl
        self.session_ttl = session_ttl
        self.session = None
        self.session_expires_at = 0.0

    def exchange(self, token):
        if not isinstance(token, str) or self.token is None or self.clock() >= self.expires_at:
            return None
        if not secrets.compare_digest(token.encode(), self.token.encode()):
            return None
        self.token = None
        self.session = secrets.token_urlsafe(32)
        self.session_expires_at = self.clock() + self.session_ttl
        return self.session

    def authorized(self, session):
        return bool(isinstance(session, str) and self.session and
                    self.clock() < self.session_expires_at and
                    secrets.compare_digest(session.encode(), self.session.encode()))

    def revoke(self):
        self.token = None
        self.session = None
        self.session_expires_at = 0.0


class PairingLimiter:
    """Bounded per-address rate limiting for the unauthenticated pairing route."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.attempts = OrderedDict()

    def allow(self, address):
        now = self.clock()
        times = self.attempts.pop(address, deque())
        while times and times[0] <= now - 60:
            times.popleft()
        allowed = len(times) < 10
        if allowed:
            times.append(now)
        self.attempts[address] = times
        while len(self.attempts) > 1024:
            self.attempts.popitem(last=False)
        return allowed
