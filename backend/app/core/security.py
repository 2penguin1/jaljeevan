"""Passwords, session tokens and a brake on password guessing.

Passwords are stored only as bcrypt hashes. A session is a signed JWT (HS256, 12 hours) kept in an httpOnly cookie,
so page scripts cannot read it. JWT_SECRET must be set on servers; local runs and tests use a fixed development key.
"""
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

DEV_KEY = "dev-only-signing-key-not-for-servers-0123456789"
TTL_SECONDS = 12 * 3600
COOKIE = "session"


class InvalidToken(Exception):
    """Missing, tampered or expired session."""


@dataclass(frozen=True)
class Claims:
    user_id: uuid.UUID
    role: str
    org_id: uuid.UUID | None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:  # "!" or any non-bcrypt value: the account has no password and cannot log in
        return False


def signing_key() -> str:
    if not settings.jwt_secret and settings.cookie_secure:  # a server without its own key would accept forged tokens
        raise RuntimeError("JWT_SECRET is not set")
    return settings.jwt_secret or DEV_KEY


def issue_token(user_id: uuid.UUID, role: str, org_id: uuid.UUID | None, key: str | None = None,
                ttl_seconds: int = TTL_SECONDS) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "role": role, "org": str(org_id) if org_id else None,
              "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
    return jwt.encode(claims, key or signing_key(), algorithm="HS256")


def read_token(token: str, key: str | None = None) -> Claims:
    try:
        data = jwt.decode(token, key or signing_key(), algorithms=["HS256"], options={"require": ["sub", "exp"]})
        return Claims(uuid.UUID(data["sub"]), data["role"], uuid.UUID(data["org"]) if data.get("org") else None)
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidToken(str(exc)) from exc


class LoginBrake:
    """At most `max_failures` wrong passwords per email in `window_seconds` (per process; enough for one API task)."""

    def __init__(self, max_failures: int = 5, window_seconds: float = 60, clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window = window_seconds
        self.clock = clock
        self._failures: dict[str, deque] = defaultdict(deque)

    def allowed(self, email: str) -> bool:
        times = self._failures[email.lower()]
        while times and self.clock() - times[0] > self.window:
            times.popleft()
        return len(times) < self.max_failures

    def failed(self, email: str) -> None:
        self._failures[email.lower()].append(self.clock())
