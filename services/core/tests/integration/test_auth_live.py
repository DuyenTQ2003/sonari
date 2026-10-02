"""Auth on the real MongoDB and Redis (`make infra`): what the in-memory fakes cannot prove.

The stores' atomicity and the limiter's counting depend on the databases, so these run
only locally; CI has no MongoDB or Redis and skips the file.
"""

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import Response
from pymongo import AsyncMongoClient, MongoClient
from redis import Redis as SyncRedis
from redis.asyncio import Redis

from auth_fakes import FakeCaptcha
from auth_helpers import PASSWORD, error, login, refresh_cookie, register
from sonari_core.app import CONTEXTS, create_app
from sonari_core.identity.models import RefreshTokenDocument, User
from sonari_core.identity.passwords import PasswordHasher
from sonari_core.identity.ports import ConsumeOutcome, EmailTaken, TokenRecord
from sonari_core.identity.service import AuthConfig, AuthService
from sonari_core.identity.stores import MongoTokenStore, MongoUserStore
from sonari_core.identity.tokens import AccessTokenCodec, hash_refresh_token
from sonari_core.shared.contexts import init_contexts
from sonari_core.shared.events import RedisStreamPublisher, stream_name
from sonari_core.shared.ratelimit import RedisSlidingWindowLimiter
from sonari_core.shared.resources import build_resources
from sonari_core.shared.settings import Settings


@pytest.fixture
def run_id() -> str:
    """Prefix of everything a test creates, so it can be found and deleted afterwards."""
    return f"it-{uuid4().hex[:10]}"


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
    await RefreshTokenDocument.find({"family_id": {"$regex": f"^{run_id}"}}).delete()
    await client.close()


async def test_concurrent_registrations_of_one_email_produce_exactly_one_account(
    stores: tuple[MongoUserStore, MongoTokenStore], run_id: str
) -> None:
    users, _ = stores
    email = f"{run_id}@example.com"

    results = await asyncio.gather(
        *(users.create(email, "hash", datetime.now(UTC)) for _ in range(10)),
        return_exceptions=True,
    )

    assert sum(1 for r in results if not isinstance(r, Exception)) == 1
    assert sum(1 for r in results if isinstance(r, EmailTaken)) == 9


async def test_a_refresh_token_can_be_spent_exactly_once_under_concurrency(
    stores: tuple[MongoUserStore, MongoTokenStore], run_id: str
) -> None:
    users, tokens = stores
    now = datetime.now(UTC)
    user = await users.create(f"{run_id}@example.com", "hash", now)
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
    user = await users.create(f"{run_id}@example.com", "hash", now)

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


# --- the whole thing over HTTP -----------------------------------------------------------


@pytest.fixture
def live_client(live_settings: Settings) -> Iterator[TestClient]:
    """The real app on real MongoDB and Redis, with only the Turnstile call faked."""
    resources = build_resources(live_settings)
    assert resources.redis is not None
    service = AuthService(
        users=MongoUserStore(),
        tokens=MongoTokenStore(),
        hasher=PasswordHasher(),
        codec=AccessTokenCodec(live_settings.jwt_secret.get_secret_value(), 900),
        limiter=RedisSlidingWindowLimiter(resources.redis),
        captcha=FakeCaptcha(),
        publisher=RedisStreamPublisher(resources.redis),
        config=AuthConfig(900, 30 * 24 * 3600, 1000, 3600, 1000, 1000, 900),
    )
    app = create_app(live_settings, resources=resources, auth_service=service)
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def present(client: TestClient, token: str) -> Response:
    """Send a refresh token as a cookie header, overriding the client's own cookie jar.

    The same client throughout: each TestClient runs on its own event loop, and the
    app's MongoDB client belongs to the loop of the one that started it.
    """
    return client.post("/v1/auth/refresh", headers={"Cookie": f"refresh_token={token}"})


@pytest.fixture
def cleanup(
    mongo_client: MongoClient[dict[str, Any]], live_settings: Settings, run_id: str
) -> Iterator[None]:
    """Delete what the test created in MongoDB and Redis, whether it passed or not."""
    yield
    identity = mongo_client["identity"]
    ids = [
        u["_id"] for u in identity["users"].find({"email": {"$regex": f"^{run_id}"}}, {"_id": 1})
    ]
    identity["refresh_tokens"].delete_many({"user_id": {"$in": ids}})
    identity["users"].delete_many({"_id": {"$in": ids}})

    redis = SyncRedis.from_url(live_settings.redis_url, decode_responses=True)
    try:
        wanted = {str(user_id) for user_id in ids}
        stream = stream_name("UserRegistered")
        for entry_id, fields in redis.xrange(stream):
            if json.loads(fields["data"])["userId"] in wanted:
                redis.xdel(stream, entry_id)
        email_key = hashlib.sha256(f"{run_id}@example.com".encode()).hexdigest()[:32]
        redis.delete(
            "ratelimit:register:ip:testclient",
            "ratelimit:login:ip:testclient",
            f"ratelimit:login:email:{email_key}",
        )
    finally:
        redis.close()


def test_register_rotate_replay_and_logout_on_the_real_stack(
    live_client: TestClient,
    mongo_client: MongoClient[dict[str, Any]],
    live_settings: Settings,
    run_id: str,
    cleanup: None,
) -> None:
    email = f"{run_id}@example.com"
    registered = register(live_client, email)
    assert registered.status_code == 201
    user_id = registered.json()["user"]["id"]
    first = refresh_cookie(registered)

    rotated = live_client.post("/v1/auth/refresh")
    assert rotated.status_code == 200
    second = refresh_cookie(rotated)

    replayed = present(live_client, first)
    assert error(replayed)["code"] == "refresh_reused"
    assert present(live_client, second).status_code == 401
    assert login(live_client, email).status_code == 200  # a new login is a new family

    identity = mongo_client["identity"]
    stored = identity["users"].find_one({"email": email})
    assert stored is not None and stored["password_hash"].startswith("$argon2id$")
    assert PASSWORD not in json.dumps(stored, default=str)
    assert (
        identity["refresh_tokens"].find_one({"token_hash": first}) is None
    )  # only hashes are stored
    assert identity["refresh_tokens"].find_one({"token_hash": hash_refresh_token(first)})

    sync_redis = SyncRedis.from_url(live_settings.redis_url, decode_responses=True)
    try:
        stream = stream_name("UserRegistered")
        ours = [
            json.loads(fields["data"])
            for _, fields in sync_redis.xrange(stream)
            if json.loads(fields["data"])["userId"] == user_id
        ]
    finally:
        sync_redis.close()
    assert len(ours) == 1


def test_the_indexes_the_design_relies_on_exist(
    mongo_client: MongoClient[dict[str, Any]], live_client: TestClient
) -> None:
    users = mongo_client["identity"]["users"].index_information()
    tokens = mongo_client["identity"]["refresh_tokens"].index_information()

    assert any(i.get("unique") and i["key"] == [("email", 1)] for i in users.values())
    assert any(i.get("unique") and i["key"] == [("token_hash", 1)] for i in tokens.values())
    assert any(
        i.get("expireAfterSeconds") == 0 and i["key"] == [("expires_at", 1)]
        for i in tokens.values()
    )
