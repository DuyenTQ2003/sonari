"""Auth over HTTP on the real MongoDB and Redis (`make infra`), including the
UserRegistered event reaching Redis through the outbox relay the app runs.

CI has no MongoDB or Redis and skips the file.
"""

import hashlib
import json
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pymongo import MongoClient
from redis import Redis as SyncRedis

from auth_fakes import FakeCaptcha
from auth_helpers import PASSWORD, error, login, refresh_cookie, register
from sonari_core.app import create_app
from sonari_core.identity.passwords import PasswordHasher
from sonari_core.identity.service import AuthConfig, AuthService
from sonari_core.identity.stores import MongoTokenStore, MongoUserStore
from sonari_core.identity.tokens import AccessTokenCodec, hash_refresh_token
from sonari_core.shared.events import stream_name
from sonari_core.shared.ratelimit import RedisSlidingWindowLimiter
from sonari_core.shared.resources import build_resources
from sonari_core.shared.settings import Settings


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
    identity["outbox"].delete_many({"payload.userId": {"$in": [str(i) for i in ids]}})

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

    # The event reaches Redis through the outbox relay the app runs in the background.
    sync_redis = SyncRedis.from_url(live_settings.redis_url, decode_responses=True)
    try:
        ours = wait_for(lambda: published_for(sync_redis, user_id))
    finally:
        sync_redis.close()
    assert len(ours) == 1
    outbox_entry = identity["outbox"].find_one({"payload.userId": user_id})
    assert outbox_entry is not None and outbox_entry["sent_at"] is not None
    assert ours[0]["eventId"] == outbox_entry["_id"]


def published_for(redis: SyncRedis, user_id: str) -> list[dict[str, Any]]:
    payloads = [json.loads(f["data"]) for _, f in redis.xrange(stream_name("UserRegistered"))]
    return [p for p in payloads if p["userId"] == user_id]


def wait_for(probe: Callable[[], list[dict[str, Any]]], timeout_s: float = 5.0) -> list[Any]:
    deadline = time.monotonic() + timeout_s
    while not (found := probe()) and time.monotonic() < deadline:
        time.sleep(0.05)
    return found


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
