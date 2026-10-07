"""Speaking items on the real MongoDB (`make infra`), as the `core` user: the checks against the
pinned Source, idempotence and the script, which a pure test cannot show.

Article numbers are ones no real VOA page has; everything a test writes is deleted after.
"""

import json
import os
import random
import re
import subprocess
import sys
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest_asyncio
from pymongo import AsyncMongoClient, MongoClient

from sonari_core import content
from sonari_core.content.ingest import ingest_sources, passage_from_record
from sonari_core.content.models import Source
from sonari_core.content.speaking import SpeakingItem, SpeakingItemRecord
from sonari_core.content.speaking_ingest import ingest_items, source_problems
from source_fakes import BASE_ARTICLE, BODY, VERSION_A, make_record

NOW = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)
SENTENCE = "The students read the short test sentence."  # 7 words: as many as the line it replaces
SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "ingest_speaking_items.py"
Stored = Callable[[], tuple[str, int]]


def record_with_sentence(article: int) -> dict[str, Any]:
    """A trimmed passage whose line `BODY[3]` is a sentence with no digit, so it can be an item."""
    record = make_record(article)
    for lines in (record["original_text"], record["text"]):
        lines[lines.index(BODY[3])] = SENTENCE
    return record


def item_for(article: int, **changes: Any) -> SpeakingItemRecord:
    record = record_with_sentence(article)
    words = [
        {"text": m.group(), "start": m.start(), "end": m.end(), "tokens": [m.group().lower()]}
        for m in re.finditer(r"[A-Za-z]+", SENTENCE)
    ]
    fields: dict[str, Any] = {
        "source": f"voa:{article}@{VERSION_A}", "line": record["text"].index(SENTENCE),
        "start": 0, "unit": "Study and work", "text": SENTENCE, "words": words,
        "g2p_version": "g2p/test",
    }  # fmt: skip
    return SpeakingItemRecord.model_validate(fields | changes)


@pytest_asyncio.fixture
async def article(core_mongo_uri: str) -> AsyncIterator[int]:
    """A stored Source holding `SENTENCE`; the Source and its items are deleted after."""
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(core_mongo_uri, tz_aware=True)
    await content.SPEC.init(client)
    number = random.randrange(BASE_ARTICLE, BASE_ARTICLE + 9_000_000)
    await ingest_sources([passage_from_record(record_with_sentence(number))], NOW)
    yield number
    await SpeakingItem.find({"source": f"voa:{number}@{VERSION_A}"}).delete()
    await Source.find({"source_id": f"voa:{number}"}).delete()
    await client.close()


async def test_an_item_is_stored_once_whatever_the_number_of_runs(article: int) -> None:
    item = item_for(article)

    first = await ingest_items([item], NOW)
    second = await ingest_items([item], NOW)

    assert (first.inserted, second.inserted, second.unchanged) == (1, 0, 1)
    stored = await SpeakingItem.get(item.key)
    assert stored is not None
    assert stored.source == f"voa:{article}@{VERSION_A}" and stored.ingested_at == NOW
    assert stored.words[0].tokens == ["the"]


async def test_the_same_key_with_other_phonemes_is_a_conflict_and_the_stored_item_stays(
    article: int,
) -> None:
    await ingest_items([item_for(article)], NOW)
    changed = item_for(article)
    changed.words[0].tokens = ["different"]

    report = await ingest_items([changed], NOW)

    assert report.conflicts == [changed.key]
    stored = await SpeakingItem.get(changed.key)
    assert stored is not None and stored.words[0].tokens == ["the"]


async def test_an_item_is_checked_against_the_pinned_source(article: int) -> None:
    good = item_for(article)
    missing = item_for(article, source="voa:1@voa-trim/ffffffffffff")
    shifted = item_for(article, start=1)
    out_of_range = item_for(article, line=10_000)

    problems = await source_problems([good, missing, shifted, out_of_range])

    assert len(problems) == 3
    assert "is not in content.sources" in problems[0]
    assert "is not in voa:" in problems[1] and "is not in voa:" in problems[2]


def run_script(path: Path, mongo_uri: str, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *flags],
        env={**os.environ, "MONGO_URI_CORE": mongo_uri},
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip


def test_the_script_is_idempotent_and_refuses_an_item_whose_source_is_missing(
    core_mongo_uri: str, mongo_client: MongoClient[dict[str, Any]], tmp_path: Path
) -> None:
    number = random.randrange(BASE_ARTICLE, BASE_ARTICLE + 9_000_000)
    corpus = mongo_client["content"]["sources"]
    items = mongo_client["content"]["speaking_items"]
    corpus_file = tmp_path / "trimmed.jsonl"
    corpus_file.write_text(json.dumps(record_with_sentence(number), sort_keys=True) + "\n")
    ingest = Path(__file__).resolve().parents[4] / "scripts" / "ingest_sources.py"
    env = {**os.environ, "MONGO_URI_CORE": core_mongo_uri}
    try:
        subprocess.run([sys.executable, str(ingest), str(corpus_file)], env=env, check=True)
        good = tmp_path / "good.jsonl"
        good.write_text(item_for(number).model_dump_json() + "\n")
        orphan = tmp_path / "orphan.jsonl"
        orphan.write_text(
            item_for(number, source="voa:1@voa-trim/ffffffffffff").model_dump_json() + "\n"
        )

        first = run_script(good, core_mongo_uri)
        second = run_script(good, core_mongo_uri)
        refused = run_script(orphan, core_mongo_uri)

        assert "1 items: 1 inserted, 0 unchanged, 0 conflicts" in first.stdout
        assert "1 items: 0 inserted, 1 unchanged, 0 conflicts" in second.stdout
        assert (first.returncode, second.returncode) == (0, 0)
        assert refused.returncode == 1 and "is not in content.sources" in refused.stderr
        assert items.count_documents({"source": f"voa:{number}@{VERSION_A}"}) == 1
    finally:
        items.delete_many({"source": {"$regex": f"^voa:{number}@"}})
        corpus.delete_many({"source_id": f"voa:{number}"})
