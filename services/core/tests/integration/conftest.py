"""Fixtures for integration tests that need the dev MongoDB and Redis from compose.yaml.

On a developer machine the tests skip, with the reason, when MongoDB or Redis is not set up
or not reachable. In CI (`CI` is set) the same condition fails the test: the workflow starts
both with `make infra`, so an unreachable service is broken infrastructure, and a skip would
let the transactional outbox go unverified while the pipeline stays green. They also fail
when MongoDB answers but refuses the core service user.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NoReturn

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ServerSelectionTimeoutError
from redis import Redis as SyncRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from sonari_core.shared.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[4]
URI_VARIABLE = "MONGO_URI_CORE"

Documents = Collection[dict[str, Any]]


def unavailable(reason: str) -> NoReturn:
    """Skip the test on a developer machine; fail it in CI, which must provide the service."""
    if os.environ.get("CI"):
        pytest.fail(
            f"{reason} (CI must start the services: see .github/workflows/ci.yml)", pytrace=False
        )
    pytest.skip(reason)


def env_value(variable: str) -> str | None:
    """A setting from the environment first, then from the repo `.env`."""
    from_environment = os.environ.get(variable)
    if from_environment:
        return from_environment
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == variable:
                return value.strip()
    return None


@pytest.fixture(scope="session")
def mongo_client() -> Iterator[MongoClient[dict[str, Any]]]:
    uri = env_value(URI_VARIABLE)
    if uri is None:
        unavailable(f"{URI_VARIABLE} is not set: copy .env.example to .env and run `make infra`")
    client: MongoClient[dict[str, Any]] = MongoClient(uri, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        client.close()
        unavailable("MongoDB is not reachable on the dev port: start it with `make infra`")
    yield client
    client.close()


@pytest.fixture
def scratch_collections(
    mongo_client: MongoClient[dict[str, Any]],
) -> Iterator[tuple[Documents, Documents]]:
    """Two throwaway collections in the `learning` database, dropped after the test.

    They exist before the test body runs, so a rolled-back transaction is judged on its
    documents and not on whether the collection was created.
    """
    database = mongo_client["learning"]
    suffix = uuid.uuid4().hex[:8]
    progress = database.create_collection(f"it_progress_{suffix}")
    review_log = database.create_collection(f"it_review_log_{suffix}")
    yield progress, review_log
    progress.drop()
    review_log.drop()


@pytest.fixture
def live_settings(mongo_client: MongoClient[dict[str, Any]]) -> Settings:
    """Settings for the real dev MongoDB and Redis; skips when Redis is not reachable.

    Depending on `mongo_client` means the test is skipped first when MongoDB is down.
    """
    redis_url = env_value("REDIS_URL")
    if redis_url is None:
        unavailable("REDIS_URL is not set: copy .env.example to .env and run `make infra`")
    probe = SyncRedis.from_url(redis_url, socket_connect_timeout=2)
    try:
        probe.ping()
    except RedisConnectionError:
        unavailable("Redis is not reachable on the dev port: start it with `make infra`")
    finally:
        probe.close()
    mongo_uri = env_value(URI_VARIABLE)
    jwt_secret = env_value("JWT_SECRET")
    turnstile_secret = env_value("TURNSTILE_SECRET_KEY")
    assert mongo_uri is not None
    if jwt_secret is None or turnstile_secret is None:
        unavailable("JWT_SECRET or TURNSTILE_SECRET_KEY is missing: copy them from .env.example")
    return Settings(
        mongo_uri=mongo_uri,
        redis_url=redis_url,
        jwt_secret=jwt_secret,
        turnstile_secret=turnstile_secret,
        otel_enabled=False,
    )


@pytest.fixture
def run_id() -> str:
    """Prefix of everything a test creates, so it can be found and deleted afterwards."""
    return f"it-{uuid.uuid4().hex[:10]}"
