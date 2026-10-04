"""Source ingest on the real MongoDB (`make infra`), as the `core` user: what the pure tests
cannot prove. Idempotence, the re-trim policy of ADR-0010 and the index that guards it all
depend on the database.

Every test uses article numbers no real VOA page has, and deletes what it wrote.
"""

import asyncio
import random
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from sonari_core import content
from sonari_core.content.ingest import ingest_sources, passage_from_record
from sonari_core.content.models import Source, TrimmedPassage
from source_fakes import BASE_ARTICLE, VERSION_A, VERSION_B, make_record

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)
Articles = Callable[[int], list[int]]


def passage(
    article: int, rules_version: str = VERSION_A, remove: tuple[int, ...] = (0, -1)
) -> TrimmedPassage:
    return passage_from_record(make_record(article, rules_version, remove=remove))


@pytest_asyncio.fixture
async def articles(core_mongo_uri: str) -> AsyncIterator[Articles]:
    """Binds `Source` to the `content` database and hands out fresh article numbers."""
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(core_mongo_uri, tz_aware=True)
    await content.SPEC.init(client)
    issued: list[int] = []

    def issue(count: int) -> list[int]:
        numbers = random.sample(range(BASE_ARTICLE, BASE_ARTICLE + 9_000_000), count)
        issued.extend(numbers)
        return numbers

    yield issue
    await Source.find({"source_id": {"$in": [f"voa:{n}" for n in issued]}}).delete()
    await client.close()


async def stored(numbers: Sequence[int]) -> list[Source]:
    return await Source.find({"source_id": {"$in": [f"voa:{n}" for n in numbers]}}).to_list()


async def test_a_first_ingest_stores_every_passage_as_the_current_source(
    articles: Articles,
) -> None:
    numbers = articles(5)
    passages = [passage(n) for n in numbers]

    report = await ingest_sources(passages, NOW)

    assert (report.inserted, report.superseded, report.unchanged, report.conflicts) == (5, 0, 0, [])
    documents = await stored(numbers)
    assert sorted(d.id for d in documents) == sorted(p.key for p in passages)
    assert all(d.current and d.ingested_at == NOW for d in documents)


async def test_a_stored_source_keeps_the_passage_it_was_made_from(articles: Articles) -> None:
    (number,) = articles(1)
    original = passage(number)
    await ingest_sources([original], NOW)

    read_back = await Source.get_current(original.source_id)

    assert read_back is not None
    assert read_back.id == original.key
    assert read_back.model_dump(include=set(TrimmedPassage.model_fields)) == original.model_dump()
    raw = await Source.get_pymongo_collection().find_one({"_id": original.key})
    assert raw is not None
    assert raw["trim"]["removed"][0]["text"] == original.original_text[0]  # auditable in place


async def test_ingesting_the_same_file_twice_leaves_the_same_documents(articles: Articles) -> None:
    numbers = articles(25)
    passages = [passage(n) for n in numbers]

    first = await ingest_sources(passages, NOW)
    second = await ingest_sources(passages, NOW + timedelta(hours=1))

    assert (first.inserted, first.unchanged) == (25, 0)
    assert (second.inserted, second.superseded, second.unchanged) == (0, 0, 25)
    documents = await stored(numbers)
    assert len(documents) == 25
    assert {d.ingested_at for d in documents} == {NOW}  # the second run wrote nothing


async def test_a_retrim_under_a_new_rules_version_keeps_both_and_moves_current(
    articles: Articles,
) -> None:
    numbers = articles(3)
    await ingest_sources([passage(n, VERSION_A) for n in numbers], NOW)

    report = await ingest_sources(
        [passage(n, VERSION_B, remove=(0, 1, -1)) for n in numbers], NOW + timedelta(days=1)
    )

    assert (report.inserted, report.superseded, report.unchanged) == (0, 3, 0)
    documents = await stored(numbers)
    assert len(documents) == 6
    for number in numbers:
        current = await Source.get_current(f"voa:{number}")
        assert current is not None
        assert current.trim.rules_version == VERSION_B
        old = next(
            d for d in documents if d.source_id == f"voa:{number}" and d.id.endswith(VERSION_A)
        )
        assert old.current is False
        assert old.text != current.text  # the old trim is intact, not overwritten
    assert sum(d.current for d in documents) == 3


async def test_ingesting_the_old_version_again_restores_it_without_a_new_document(
    articles: Articles,
) -> None:
    numbers = articles(3)
    await ingest_sources([passage(n, VERSION_A) for n in numbers], NOW)
    await ingest_sources([passage(n, VERSION_B, remove=(0, 1, -1)) for n in numbers], NOW)

    report = await ingest_sources([passage(n, VERSION_A) for n in numbers], NOW)

    assert (report.inserted, report.superseded, report.unchanged) == (0, 3, 0)
    documents = await stored(numbers)
    assert len(documents) == 6
    assert {d.trim.rules_version for d in documents if d.current} == {VERSION_A}


async def test_the_same_version_with_different_content_is_a_conflict_and_changes_nothing(
    articles: Articles,
) -> None:
    (number,) = articles(1)
    await ingest_sources([passage(number)], NOW)
    changed = passage(number).model_copy(update={"title": "A title the first run never saw"})

    report = await ingest_sources([changed], NOW + timedelta(hours=1))

    assert report.conflicts == [changed.key]
    assert (report.inserted, report.superseded, report.unchanged) == (0, 0, 0)
    (document,) = await stored([number])
    assert document.title == f"Test passage {number}"


async def test_the_database_itself_refuses_a_second_current_version(articles: Articles) -> None:
    (number,) = articles(1)
    await ingest_sources([passage(number, VERSION_A)], NOW)
    rival = passage(number, VERSION_B)

    with pytest.raises(DuplicateKeyError):
        await Source(id=rival.key, current=True, ingested_at=NOW, **rival.model_dump()).insert()


async def test_two_ingests_at_once_leave_one_document_per_passage(articles: Articles) -> None:
    numbers = articles(20)
    passages = [passage(n) for n in numbers]

    reports = await asyncio.gather(ingest_sources(passages, NOW), ingest_sources(passages, NOW))

    assert sum(r.inserted for r in reports) == 20
    assert sum(r.unchanged for r in reports) == 20
    assert not any(r.conflicts for r in reports)
    documents = await stored(numbers)
    assert len(documents) == 20
    assert all(d.current for d in documents)


async def test_the_collection_has_the_id_and_one_partial_unique_index(articles: Articles) -> None:
    articles(0)  # binds Source and creates its indexes

    indexes = await Source.get_pymongo_collection().index_information()

    assert set(indexes) == {"_id_", "source_id_current"}
    assert indexes["source_id_current"]["key"] == [("source_id", 1)]
    assert indexes["source_id_current"]["unique"] is True
    assert indexes["source_id_current"]["partialFilterExpression"] == {"current": True}
