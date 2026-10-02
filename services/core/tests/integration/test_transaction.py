"""A multi-document transaction in one context database (`learning`).

The outbox pattern in ADR-0001 needs a state change and an event row to commit or roll
back together, which MongoDB only offers on a replica set. These tests fail on a
standalone mongod.
"""

from typing import Any

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection

Documents = Collection[dict[str, Any]]


class Rollback(Exception):
    """Raised inside a transaction to force an abort."""


def test_committed_transaction_persists_every_write(
    mongo_client: MongoClient[dict[str, Any]],
    scratch_collections: tuple[Documents, Documents],
) -> None:
    progress, review_log = scratch_collections

    with mongo_client.start_session() as session, session.start_transaction():
        progress.insert_one({"_id": "p1", "lesson": "l1"}, session=session)
        review_log.insert_one({"_id": "r1", "card": "c1"}, session=session)
        # Another reader must not see the writes before the commit.
        assert progress.count_documents({}) == 0
        assert review_log.count_documents({}) == 0

    assert progress.count_documents({}) == 1
    assert review_log.count_documents({}) == 1


def test_aborted_transaction_leaves_no_data(
    mongo_client: MongoClient[dict[str, Any]],
    scratch_collections: tuple[Documents, Documents],
) -> None:
    progress, review_log = scratch_collections

    with (
        mongo_client.start_session() as session,
        pytest.raises(Rollback),
        session.start_transaction(),
    ):
        progress.insert_one({"_id": "p1", "lesson": "l1"}, session=session)
        review_log.insert_one({"_id": "r1", "card": "c1"}, session=session)
        raise Rollback

    assert progress.count_documents({}) == 0
    assert review_log.count_documents({}) == 0
