"""The application against the real dev MongoDB and Redis (`make infra`), as the `core` user."""

import asyncio
import json
import os
import subprocess
import sys
from typing import Any

from fastapi.testclient import TestClient
from pymongo import AsyncMongoClient
from redis.asyncio import Redis

from sonari_core.app import CONTEXTS, create_app
from sonari_core.shared.resources import (
    MongoReadiness,
    RedisReadiness,
    Resources,
    build_resources,
)
from sonari_core.shared.settings import Settings


def test_app_starts_initialises_every_context_and_is_ready(live_settings: Settings) -> None:
    app = create_app(live_settings)

    with TestClient(app) as client:  # the lifespan opens the clients and runs Beanie init
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"mongo": "ok", "redis": "ok"}}
    assert len(CONTEXTS) == 5


def test_readyz_reports_the_real_mongo_as_down_within_the_timeout(live_settings: Settings) -> None:
    # Nothing listens on port 1. The driver would wait 30 s by default; readiness must not.
    dead_mongo: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        "mongodb://127.0.0.1:1/?directConnection=true", serverSelectionTimeoutMS=300
    )
    redis: Redis = Redis.from_url(live_settings.redis_url, decode_responses=True)
    resources = Resources(
        readiness={"mongo": MongoReadiness(dead_mongo), "redis": RedisReadiness(redis)}
    )
    settings = live_settings.model_copy(update={"readiness_timeout_s": 1.0})

    with TestClient(create_app(settings, resources=resources)) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["details"]["checks"] == {"mongo": "down", "redis": "ok"}


# Run in a fresh interpreter: PyMongo's instrumentation binds to the first tracer provider it
# sees and cannot be unregistered, so this check is only reliable in a process of its own.
TRACED_SYSTEMS_SCRIPT = """
import json

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from sonari_core.app import create_app
from sonari_core.shared.settings import Settings

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
with TestClient(create_app(Settings(), tracer_provider=provider)) as client:
    client.get("/readyz")  # not traced itself, but its pings run inside the clients
spans = exporter.get_finished_spans()
attributes = [s.attributes for s in spans if s.attributes]
print(json.dumps(sorted({a["db.system"] for a in attributes if "db.system" in a})))
"""


def test_database_calls_are_traced_for_the_async_mongo_and_redis_clients(
    live_settings: Settings,
) -> None:
    """The instrumentation must see the clients this service really uses, not just sync ones."""
    environment = {
        **os.environ,
        "MONGO_URI_CORE": live_settings.mongo_uri,
        "REDIS_URL": live_settings.redis_url,
        "OTEL_ENABLED": "true",
    }

    result = subprocess.run(
        [sys.executable, "-c", TRACED_SYSTEMS_SCRIPT],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout.splitlines()[-1]) == ["mongodb", "redis"]


def test_build_resources_makes_real_clients_that_answer(live_settings: Settings) -> None:
    async def ping_both() -> None:
        resources = build_resources(live_settings)
        try:
            for check in resources.readiness.values():
                await check.ping()
        finally:
            await resources.close()

    asyncio.run(ping_both())
