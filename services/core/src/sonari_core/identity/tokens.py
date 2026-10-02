"""Access tokens (JWT, short-lived) and refresh tokens (opaque, stored hashed)."""

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt

from sonari_core.shared.errors import AppError
from sonari_core.shared.message_keys import MessageKey

Clock = Callable[[], datetime]
_BEARER = {"WWW-Authenticate": "Bearer"}


def utc_now() -> datetime:
    return datetime.now(UTC)


class AccessTokenCodec:
    ALGORITHM = "HS256"

    def __init__(self, secret: str, ttl_s: int, clock: Clock = utc_now) -> None:
        self._secret = secret
        self._ttl = timedelta(seconds=ttl_s)
        self._clock = clock

    def issue(self, user_id: str) -> str:
        now = self._clock()
        claims = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + self._ttl).timestamp()),
        }
        return jwt.encode(claims, self._secret, algorithm=self.ALGORITHM)

    def verify(self, token: str) -> str:
        """The user id in a valid, unexpired token; raises AppError(401) otherwise."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self.ALGORITHM],  # pinned: a token claiming "none" is rejected
                # Expiry is checked below against the injected clock, not the wall clock.
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
        except jwt.InvalidTokenError:
            raise AppError(
                401, "token_invalid", MessageKey.AUTH_TOKEN_INVALID, headers=_BEARER
            ) from None
        subject = claims["sub"]
        if not isinstance(subject, str) or not isinstance(claims["exp"], int):
            raise AppError(401, "token_invalid", MessageKey.AUTH_TOKEN_INVALID, headers=_BEARER)
        if claims["exp"] <= self._clock().timestamp():
            raise AppError(401, "token_expired", MessageKey.AUTH_TOKEN_EXPIRED, headers=_BEARER)
        return subject


def hash_refresh_token(raw: str) -> str:
    """SHA-256 is enough: the token is 256 random bits, so there is nothing to brute-force."""
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """A fresh token as (raw value for the cookie, hash for the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)
