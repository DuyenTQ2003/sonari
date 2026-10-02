"""The auth rules: register, login, refresh with rotation and reuse detection, logout."""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sonari_core.identity.captcha import CaptchaUnavailable, CaptchaVerifier
from sonari_core.identity.events import EVENT_TYPE, UserRegistered
from sonari_core.identity.passwords import PasswordHasher
from sonari_core.identity.ports import (
    ConsumeOutcome,
    EmailTaken,
    TokenRecord,
    TokenStore,
    UserRecord,
    UserStore,
)
from sonari_core.identity.tokens import (
    AccessTokenCodec,
    Clock,
    hash_refresh_token,
    new_refresh_token,
    utc_now,
)
from sonari_core.shared.errors import AppError
from sonari_core.shared.events import EventPublisher
from sonari_core.shared.message_keys import MessageKey
from sonari_core.shared.ratelimit import RateLimiter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthConfig:
    access_ttl_s: int
    refresh_ttl_s: int
    register_limit: int
    register_window_s: int
    login_ip_limit: int
    login_email_limit: int
    login_window_s: int


@dataclass(frozen=True)
class Session:
    """A signed-in user with the two tokens the client needs."""

    user: UserRecord
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_max_age_s: int


def _normalise(email: str) -> str:
    return email.strip().lower()


def _fingerprint(email: str) -> str:
    """Rate-limit key for an email, so Redis never holds the address itself."""
    return hashlib.sha256(email.encode()).hexdigest()[:32]


class AuthService:
    def __init__(
        self,
        *,
        users: UserStore,
        tokens: TokenStore,
        hasher: PasswordHasher,
        codec: AccessTokenCodec,
        limiter: RateLimiter,
        captcha: CaptchaVerifier,
        publisher: EventPublisher,
        config: AuthConfig,
        clock: Clock = utc_now,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._hasher = hasher
        self._codec = codec
        self._limiter = limiter
        self._captcha = captcha
        self._publisher = publisher
        self._config = config
        self._clock = clock

    async def register(
        self, email: str, password: str, captcha_token: str, client_ip: str
    ) -> Session:
        email = _normalise(email)
        await self._limit(
            f"register:ip:{client_ip}", self._config.register_limit, self._config.register_window_s
        )
        try:
            human = await self._captcha.verify(captcha_token, client_ip)
        except CaptchaUnavailable:
            raise AppError(
                503, "captcha_unavailable", MessageKey.AUTH_CAPTCHA_UNAVAILABLE
            ) from None
        if not human:
            raise AppError(400, "captcha_failed", MessageKey.AUTH_CAPTCHA_FAILED)

        password_hash = await self._hasher.hash(password)
        try:
            user = await self._users.create(email, password_hash, self._clock())
        except EmailTaken:
            raise AppError(409, "email_taken", MessageKey.AUTH_EMAIL_TAKEN) from None

        await self._announce(user)
        return await self._start_session(user, family_id=None)

    async def login(self, email: str, password: str, client_ip: str) -> Session:
        email = _normalise(email)
        window = self._config.login_window_s
        await self._limit(f"login:ip:{client_ip}", self._config.login_ip_limit, window)
        await self._limit(
            f"login:email:{_fingerprint(email)}", self._config.login_email_limit, window
        )

        user = await self._users.find_by_email(email)
        if user is None:
            await self._hasher.verify_unknown(password)
            raise _invalid_credentials()
        if not await self._hasher.verify(user.password_hash, password):
            raise _invalid_credentials()
        return await self._start_session(user, family_id=None)

    async def refresh(self, raw_token: str | None) -> Session:
        """Swap a refresh token for a new access token and a new refresh token.

        A refresh token works once. Presenting one that was already used means it was
        copied, so the whole family is revoked and the legitimate holder signs in again.
        """
        if not raw_token:
            raise _session_invalid("refresh_invalid")
        now = self._clock()
        result = await self._tokens.consume(hash_refresh_token(raw_token), now)
        record = result.record

        if result.outcome is ConsumeOutcome.ROTATED and record is not None:
            user = await self._users.get(record.user_id)
            if user is None:
                await self._tokens.revoke_family(record.family_id, now)
                raise _session_invalid("refresh_invalid")
            return await self._start_session(user, family_id=record.family_id)

        if result.outcome is ConsumeOutcome.REUSED and record is not None:
            await self._tokens.revoke_family(record.family_id, now)
            logger.warning(
                "refresh token reuse detected, family revoked",
                extra={"family_id": record.family_id, "user_id": record.user_id},
            )
            raise _session_invalid("refresh_reused")
        raise _session_invalid("refresh_invalid")

    async def logout(self, raw_token: str | None) -> None:
        """End the session the token belongs to. Never fails: logging out twice is fine."""
        if not raw_token:
            return
        record = await self._tokens.find(hash_refresh_token(raw_token))
        if record is not None:
            await self._tokens.revoke_family(record.family_id, self._clock())

    async def authenticate(self, access_token: str) -> UserRecord:
        user = await self._users.get(self._codec.verify(access_token))
        if user is None:
            raise AppError(401, "token_invalid", MessageKey.AUTH_TOKEN_INVALID)
        return user

    async def _start_session(self, user: UserRecord, family_id: str | None) -> Session:
        now = self._clock()
        raw, hashed = new_refresh_token()
        record = TokenRecord(
            token_hash=hashed,
            family_id=family_id or uuid.uuid4().hex,  # a new login starts a new family
            user_id=user.id,
            issued_at=now,
            expires_at=now + timedelta(seconds=self._config.refresh_ttl_s),
        )
        await self._tokens.add(record)
        return Session(
            user=user,
            access_token=self._codec.issue(user.id),
            expires_in=self._config.access_ttl_s,
            refresh_token=raw,
            refresh_max_age_s=self._config.refresh_ttl_s,
        )

    async def _limit(self, key: str, limit: int, window_s: int) -> None:
        decision = await self._limiter.hit(key, limit, window_s)
        if not decision.allowed:
            raise AppError(
                429,
                "rate_limited",
                MessageKey.AUTH_RATE_LIMITED,
                {"retryAfterSeconds": decision.retry_after_s},
                {"Retry-After": str(decision.retry_after_s)},
            )

    async def _announce(self, user: UserRecord) -> None:
        """Best effort: the account exists either way. The outbox (P15) makes this reliable."""
        try:
            event = UserRegistered.now(user.id, self._clock())
            await self._publisher.publish(EVENT_TYPE, event.model_dump(mode="json", by_alias=True))
        except Exception:
            logger.exception("could not publish UserRegistered", extra={"user_id": user.id})


def _invalid_credentials() -> AppError:
    # The same answer whether the email is unknown or the password is wrong.
    return AppError(401, "invalid_credentials", MessageKey.AUTH_INVALID_CREDENTIALS)


def _session_invalid(code: str) -> AppError:
    return AppError(401, code, MessageKey.AUTH_SESSION_INVALID)
