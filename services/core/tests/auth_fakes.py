"""In-memory stand-ins for the auth service's dependencies, so its rules run in CI.

The stores and the limiter follow the same contracts as the MongoDB and Redis ones, which
tests/integration/test_auth_live.py exercises for real.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher as Argon2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from event_fakes import InMemoryOutbox
from sonari_core.app import create_app
from sonari_core.identity.captcha import CaptchaUnavailable
from sonari_core.identity.passwords import PasswordHasher
from sonari_core.identity.ports import (
    Announce,
    ConsumeOutcome,
    ConsumeResult,
    EmailTaken,
    TokenRecord,
    UserRecord,
)
from sonari_core.identity.service import AuthConfig, AuthService
from sonari_core.identity.tokens import AccessTokenCodec
from sonari_core.shared.ratelimit import RateDecision
from sonari_core.shared.resources import Resources
from sonari_core.shared.settings import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class InMemoryUserStore:
    """Writes the user and its outbox entry together, as the Mongo store's transaction does."""

    def __init__(self, outbox: InMemoryOutbox) -> None:
        self.by_email: dict[str, UserRecord] = {}
        self.outbox = outbox

    async def create(
        self, email: str, password_hash: str, now: datetime, announce: Announce
    ) -> UserRecord:
        if email in self.by_email:
            raise EmailTaken(email)
        user = UserRecord(f"user-{len(self.by_email) + 1}", email, password_hash, now)
        message = announce(user)  # built first: if it raises, neither write happens
        self.by_email[email] = user
        self.outbox.add(message)
        return user

    async def find_by_email(self, email: str) -> UserRecord | None:
        return self.by_email.get(email)

    async def get(self, user_id: str) -> UserRecord | None:
        return next((u for u in self.by_email.values() if u.id == user_id), None)


class InMemoryTokenStore:
    def __init__(self) -> None:
        self.records: dict[str, TokenRecord] = {}

    async def add(self, record: TokenRecord) -> None:
        self.records[record.token_hash] = record

    async def find(self, token_hash: str) -> TokenRecord | None:
        return self.records.get(token_hash)

    async def consume(self, token_hash: str, now: datetime) -> ConsumeResult:
        record = self.records.get(token_hash)
        if record is None:
            return ConsumeResult(ConsumeOutcome.NOT_FOUND)
        if record.rotated_at is not None or record.revoked_at is not None:
            return ConsumeResult(ConsumeOutcome.REUSED, record)
        if record.expires_at <= now:
            return ConsumeResult(ConsumeOutcome.EXPIRED, record)
        spent = replace(record, rotated_at=now)
        self.records[token_hash] = spent
        return ConsumeResult(ConsumeOutcome.ROTATED, spent)

    async def revoke_family(self, family_id: str, now: datetime) -> None:
        for key, record in self.records.items():
            if record.family_id == family_id and record.revoked_at is None:
                self.records[key] = replace(record, revoked_at=now)

    def family(self, family_id: str) -> list[TokenRecord]:
        return [r for r in self.records.values() if r.family_id == family_id]


class FakeLimiter:
    """Sliding window on the fake clock; refused hits do not count, as in the Redis one."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)

    async def hit(self, key: str, limit: int, window_s: int) -> RateDecision:
        now = self._clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - timedelta(seconds=window_s):
            hits.popleft()
        if len(hits) >= limit:
            wait = hits[0] + timedelta(seconds=window_s) - now
            return RateDecision(False, max(int(wait.total_seconds() + 0.999), 1))
        hits.append(now)
        return RateDecision(True)


class FakeCaptcha:
    def __init__(self) -> None:
        self.passes = True
        self.unavailable = False
        self.calls: list[tuple[str, str | None]] = []

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        self.calls.append((token, remote_ip))
        if self.unavailable:
            raise CaptchaUnavailable
        return self.passes


class CountingHasher(PasswordHasher):
    """Cheap argon2id parameters for speed, and a count of decoy checks."""

    def __init__(self) -> None:
        super().__init__(Argon2(time_cost=1, memory_cost=8, parallelism=1))
        self.decoy_checks = 0

    async def verify_unknown(self, password: str) -> None:
        self.decoy_checks += 1
        await super().verify_unknown(password)


@dataclass
class AuthKit:
    """An app wired to the fakes above, with handles to inspect and steer them."""

    app: FastAPI
    clock: FakeClock
    users: InMemoryUserStore
    tokens: InMemoryTokenStore
    limiter: FakeLimiter
    captcha: FakeCaptcha
    outbox: InMemoryOutbox
    hasher: CountingHasher
    settings: Settings

    def client(self, ip: str = "testclient") -> TestClient:
        """A browser-like client. https, so the Secure refresh cookie is sent back."""
        return TestClient(
            self.app,
            base_url="https://testserver",
            client=(ip, 50000),
            raise_server_exceptions=False,
        )


def build_auth_kit(settings: Settings) -> AuthKit:
    clock = FakeClock()
    outbox = InMemoryOutbox()
    users, tokens = InMemoryUserStore(outbox), InMemoryTokenStore()
    limiter, captcha = FakeLimiter(clock), FakeCaptcha()
    hasher = CountingHasher()
    service = AuthService(
        users=users,
        tokens=tokens,
        hasher=hasher,
        codec=AccessTokenCodec(
            settings.jwt_secret.get_secret_value(), settings.access_token_ttl_s, clock
        ),
        limiter=limiter,
        captcha=captcha,
        config=AuthConfig(
            access_ttl_s=settings.access_token_ttl_s,
            refresh_ttl_s=settings.refresh_token_ttl_s,
            register_limit=settings.register_limit,
            register_window_s=settings.register_window_s,
            login_ip_limit=settings.login_ip_limit,
            login_email_limit=settings.login_email_limit,
            login_window_s=settings.login_window_s,
        ),
        clock=clock,
    )
    app = create_app(
        settings,
        resources=Resources(readiness={}),
        auth_service=service,
    )
    return AuthKit(app, clock, users, tokens, limiter, captcha, outbox, hasher, settings)
