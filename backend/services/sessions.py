"""Authentication sessions are distinct from commercial ledger sessions."""

import hashlib
import math
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from backend.services.errors import LedgerError
from backend.services.passwords import Credential

COOKIE_NAME = "__Host-ledger"
SESSION_LIFETIME = 8 * 60 * 60
IDLE_LIFETIME = 30 * 60


@dataclass
class Session:
    expires: float
    last_activity: float


@dataclass(frozen=True)
class Login:
    token: str = field(repr=False)


class LoginLimit(LedgerError):
    def __init__(self, seconds: int):
        super().__init__("demasiados intentos; espere antes de reintentar", 429)
        self.seconds = seconds


class AuthService:
    def __init__(self, credential: Credential, clock: Callable[[], float] = time.monotonic):
        self.credential = credential
        self.clock = clock
        self.lock = threading.Lock()
        self.hash_lock = threading.Lock()
        self.sessions: dict[bytes, Session] = {}
        self.window = clock()
        self.attempts = 0

    def login(self, password: str, prior_token: str = "") -> Login:
        with self.lock:
            now = self.clock()
            if now - self.window >= 60:
                self.window, self.attempts = now, 0
            if self.attempts >= 5:
                raise LoginLimit(max(1, math.ceil(60 - (now - self.window))))
            self.attempts += 1
        # Hashing happens on route worker threads, never on the ASGI event loop.
        # Only one 64 MiB calculation runs at a time; session lookups stay fast.
        with self.hash_lock:
            valid = self.credential.verify(password)
        if not valid:
            raise LedgerError("contraseña incorrecta", 401)
        with self.lock:
            now = self.clock()
            self.sessions = {
                key: session for key, session in self.sessions.items() if self.active(session, now)
            }
            if prior_token:
                self.sessions.pop(self.token_key(prior_token), None)
            if len(self.sessions) >= 64:
                raise LedgerError("límite de sesiones alcanzado", 429)
            token = secrets.token_hex(32)
            self.sessions[self.token_key(token)] = Session(now + SESSION_LIFETIME, now)
            return Login(token)

    @staticmethod
    def token_key(token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    @staticmethod
    def active(session: Session, now: float) -> bool:
        return now < session.expires and now - session.last_activity < IDLE_LIFETIME

    def authenticate(self, token: str) -> bool:
        if len(token) != 64:
            return False
        key = self.token_key(token)
        with self.lock:
            session = self.sessions.get(key)
            now = self.clock()
            if session is None:
                return False
            if not self.active(session, now):
                self.sessions.pop(key)
                return False
            session.last_activity = now
            return True
