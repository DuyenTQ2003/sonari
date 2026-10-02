"""Auth on the real MongoDB and Redis (`make infra`): what the in-memory fakes cannot prove.

The stores' atomicity and the limiter's counting depend on the databases, so these run
only locally; CI has no MongoDB or Redis and skips the file.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest_asyncio
from pymongo import AsyncMongoClient
from redis.asyncio import Redis

from sonari_core.app import CONTEXTS
from sonari_core.identity.models import RefreshTokenDocument, User
from sonari_core.identity.ports import ConsumeOutcome, EmailTaken, TokenRecord, UserRecord
from sonari_core.identity.stores import MongoTokenStore, MongoUserStore
from sonari_core.identity.tokens import hash_refresh_token
from sonari_core.shared.contexts import init_contexts
from sonari_core.shared.events import EventMessage
from sonari_core.shared.ratelimit import RedisSlidingWindowLimiter
from sonari_core.shared.settings import Settings


def announce(user: UserRecord) -> EventMessage:
    """An outbox entry the cleanup can find: its id starts with the user's email."""
    return EventMessage(f"{user.email}-{uuid4().hex}", "ItUserCreated", {"userId": user.id})


# --- the stores, under real concurrency -------------------------------------------------


@pytest_asyncio.fixture
async def stores(
    live_settings: Settings, run_id: str
) -> AsyncIterator[tuple[MongoUserStore, MongoTokenStore]]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        live_settings.mongo_uri, tz_aware=True
    )
    await init_contexts(client, CONTEXTS)
    yield MongoUserStore(), MongoTokenStore()
    await User.find({"email": {"$regex": f"^{run_id}"}}).delete()
    await client["identity"]["outbox"].delete_many({"_id": {"$regex": f"^{run_id}"}})
    await RefreshTokenDocument.find({"family_id": {"$regex": f"^{run_id}"}}).delete()
    await client.close()


async def test_concurrent_registrations_of_one_email_produce_exactly_one_account(
    stores: tuple[MongoUserStore, MongoTokenStore], run_id: str
) -> None:
    users, _ = stores
    email = f"{run_id}@example.com"

    results = await asyncio.gather(
        *(users.create(email, "hash", datetime.now(UTC), announce) for _ in range(10)),
        return_exceptions=True,
    )

    assert sum(1 for r in results if not isinstance(r, Exception)) == 1
    assert sum(1 for r in results if isinstance(r, EmailTaken)) == 9


async def test_a_refresh_token_can_be_spent_exactly_once_under_concurrency(
    stores: tuple[MongoUserStore, MongoTokenStore], run_id: str
) -> None:
    users, tokens = stores
    now = datetime.now(UTC)
    user = await users.create(f"{run_id}@example.com", "hash", now, announce)
    record = TokenRecord(
        token_hash=hash_refresh_token(run_id),
        family_id=f"{run_id}-family",
        user_id=user.id,
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    await tokens.add(record)

    results = await asyncio.gather(*(tokens.consume(record.token_hash, now) for _ in range(20)))

    outcomes = [r.outcome for r in results]
    assert outcomes.count(ConsumeOutcome.ROTATED) == 1
    assert outcomes.count(ConsumeOutcome.REUSED) == 19


async def test_expired_unknown_and_revoked_tokens_are_told_apart(
    stores: tuple[MongoUserStore, MongoTokenStore], run_id: str
) -> None:
    users, tokens = stores
    now = datetime.now(UTC)
    user = await users.create(f"{run_id}@example.com", "hash", now, announce)

    def record(name: str, expires_in: timedelta) -> TokenRecord:
        return TokenRecord(
            hash_refresh_token(f"{run_id}-{name}"),
            f"{run_id}-{name}",
            user.id,
            now,
            now + expires_in,
        )

    await tokens.add(record("expired", timedelta(seconds=-1)))
    await tokens.add(record("revoked", timedelta(hours=1)))
    await tokens.revoke_family(f"{run_id}-revoked", now)

    assert (
        await tokens.consume(hash_refresh_token(f"{run_id}-expired"), now)
    ).outcome is ConsumeOutcome.EXPIRED
    assert (
        await tokens.consume(hash_refresh_token(f"{run_id}-revoked"), now)
    ).outcome is ConsumeOutcome.REUSED
    assert (
        await tokens.consume(hash_refresh_token("never-issued"), now)
    ).outcome is ConsumeOutcome.NOT_FOUND


# --- the rate limiter, on real Redis ----------------------------------------------------


@pytest_asyncio.fixture
async def redis(live_settings: Settings) -> AsyncIterator[Redis]:
    client: Redis = Redis.from_url(live_settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


class Clock:
    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


async def test_limiter_allows_the_limit_then_refuses_with_a_retry_time(
    redis: Redis, run_id: str
) -> None:
    clock = Clock()
    limiter = RedisSlidingWindowLimiter(redis, clock)
    key = f"{run_id}:basic"
    try:
        decisions = [await limiter.hit(key, 3, 10) for _ in range(5)]
    finally:
        await redis.delete(f"ratelimit:{key}")

    assert [d.allowed for d in decisions] == [True, True, True, False, False]
    assert decisions[3].retry_after_s == 10


async def test_refused_hits_do_not_extend_the_window(redis: Redis, run_id: str) -> None:
    clock = Clock()
    limiter = RedisSlidingWindowLimiter(redis, clock)
    key = f"{run_id}:slide"
    try:
        for _ in range(3):
            await limiter.hit(key, 3, 10)
        for _ in range(10):  # a burst of refused attempts a second later
            clock.now += 0.1
            assert not (await limiter.hit(key, 3, 10)).allowed
        clock.now += 10  # the three allowed hits are now older than the window
        after = await limiter.hit(key, 3, 10)
    finally:
        await redis.delete(f"ratelimit:{key}")

    assert after.allowed


async def test_exactly_the_limit_gets_through_under_concurrency(redis: Redis, run_id: str) -> None:
    limiter = RedisSlidingWindowLimiter(redis)
    key = f"{run_id}:burst"
    try:
        decisions = await asyncio.gather(*(limiter.hit(key, 5, 60) for _ in range(20)))
    finally:
        await redis.delete(f"ratelimit:{key}")

    assert sum(d.allowed for d in decisions) == 5
