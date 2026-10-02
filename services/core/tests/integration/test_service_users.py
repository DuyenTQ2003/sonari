"""The core service's MongoDB user reaches its own contexts and no others (ADR-0001).

`core` hosts identity, content, learning, gamification and analytics. `speech` is a
separate process with its own user; `tutor` waits for the ai-gateway process.
"""

from typing import Any

import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure

UNAUTHORIZED = 13
CORE_CONTEXTS = ["identity", "content", "learning", "gamification", "analytics"]
OTHER_PROCESS_CONTEXTS = ["speech", "tutor"]


@pytest.mark.parametrize("context", CORE_CONTEXTS)
def test_core_user_can_write_to_its_own_contexts(
    mongo_client: MongoClient[dict[str, Any]], context: str
) -> None:
    scratch = mongo_client[context]["it_access_check"]

    scratch.insert_one({"_id": "probe"})
    try:
        assert scratch.count_documents({}) == 1
    finally:
        scratch.drop()


@pytest.mark.parametrize("context", OTHER_PROCESS_CONTEXTS)
def test_core_user_cannot_write_to_other_processes_contexts(
    mongo_client: MongoClient[dict[str, Any]], context: str
) -> None:
    with pytest.raises(OperationFailure) as refused:
        mongo_client[context]["it_access_check"].insert_one({"_id": "probe"})

    assert refused.value.code == UNAUTHORIZED
