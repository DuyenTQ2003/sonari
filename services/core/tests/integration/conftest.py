"""Fixtures for integration tests that need the dev MongoDB from compose.yaml.

The tests skip, with the reason, when MongoDB is not set up or not reachable (CI has no
MongoDB). They fail when MongoDB answers but refuses the core service user.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ServerSelectionTimeoutError

REPO_ROOT = Path(__file__).resolve().parents[4]
URI_VARIABLE = "MONGO_URI_CORE"

Documents = Collection[dict[str, Any]]


def _core_uri() -> str | None:
    """The core service's connection string: the environment first, then the repo `.env`."""
    from_environment = os.environ.get(URI_VARIABLE)
    if from_environment:
        return from_environment
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == URI_VARIABLE:
                return value.strip()
    return None


@pytest.fixture(scope="session")
def mongo_client() -> Iterator[MongoClient[dict[str, Any]]]:
    uri = _core_uri()
    if uri is None:
        pytest.skip(f"{URI_VARIABLE} is not set: copy .env.example to .env and run `make infra`")
    client: MongoClient[dict[str, Any]] = MongoClient(uri, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        client.close()
        pytest.skip("MongoDB is not reachable on the dev port: start it with `make infra`")
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
