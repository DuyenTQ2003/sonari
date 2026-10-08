"""GET /v1/speaking-items on the real MongoDB (`make infra`), as the `core` user. No Redis is
needed: the app is built with a Mongo client only, so this runs in CI and without Docker."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pymongo import AsyncMongoClient, MongoClient

from sonari_core.app import create_app
from sonari_core.shared.resources import Resources
from sonari_core.shared.settings import Settings

IDS = ["voa:990000098@voa-trim/aaaaaaaaaaaa#2:0", "voa:990000097@voa-trim/aaaaaaaaaaaa#9:40"]


def document(item_id: str, text: str) -> dict[str, Any]:
    """A stored SpeakingItem as `scripts/ingest_speaking_items.py` writes it."""
    words = [
        {"text": m.group(), "start": m.start(), "end": m.end(), "tokens": ["x"]}
        for m in re.finditer(r"[a-z]+", text)
    ]
    return {
        "_id": item_id, "source": item_id.split("#")[0], "line": 0, "start": 0,
        "unit": "Study and work", "text": text, "words": words, "g2p_version": "g2p/test",
        "ingested_at": datetime(2026, 10, 8, tzinfo=UTC),
    }  # fmt: skip


@pytest.fixture
def stored(mongo_client: MongoClient[dict[str, Any]]) -> Iterator[None]:
    items = mongo_client["content"]["speaking_items"]
    items.delete_many({"_id": {"$in": IDS}})
    items.insert_many(
        [
            document(IDS[0], "This test sentence sorts second of all."),
            document(IDS[1], "This test sentence sorts first of all."),
        ]
    )
    yield
    items.delete_many({"_id": {"$in": IDS}})


def test_it_serves_the_stored_items_ordered_by_id(core_mongo_uri: str, stored: None) -> None:
    settings = Settings(
        mongo_uri=core_mongo_uri,
        redis_url="redis://unused.invalid",
        jwt_secret="live-test-jwt-secret-0123456789abcdef",  # type: ignore[arg-type]
        turnstile_secret="unused",  # type: ignore[arg-type]
        otel_enabled=False,
    )
    mongo: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(core_mongo_uri, tz_aware=True)

    with TestClient(create_app(settings, resources=Resources(readiness={}, mongo=mongo))) as client:
        response = client.get("/v1/speaking-items")

    assert response.status_code == 200
    ours = [item for item in response.json()["items"] if item["id"] in IDS]
    assert ours == [
        {"id": IDS[1], "text": "This test sentence sorts first of all.", "unit": "Study and work"},
        {"id": IDS[0], "text": "This test sentence sorts second of all.", "unit": "Study and work"},
    ]
