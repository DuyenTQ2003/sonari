"""Reads the trimmed VOA corpus into validated passages and stores them as `Source`
(ADR-0008, ADR-0010).

`tools/voa_corpus/write_trimmed.py` writes `trimmed.jsonl` and a `MANIFEST.json` beside it. This
module is the only reader: it checks everything that can be checked without a database, so a bad
file is refused whole and never lands partly.
"""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import Any

from pymongo.asynchronous.client_session import AsyncClientSession

from sonari_core.content.models import Source, TrimmedPassage
from sonari_core.shared.outbox import run_in_transaction

# The numeric id is VOA's own and does not change; the title slug in front of it can.
ARTICLE_URL = re.compile(r"^https://learningenglish\.voanews\.com/a/(?:[^/]+/)?(\d+)\.html$")
RECORD_FIELDS = frozenset(
    {"url", "title", "program", "fk", "words", "original_text", "text", "trim"}
)


class InvalidCorpus(Exception):
    """The file cannot be ingested. `problems` lists every reason, not just the first."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def voa_source_id(url: str) -> str:
    match = ARTICLE_URL.match(url)
    if match is None:
        raise ValueError(f"not a VOA Learning English article: {url}")
    return f"voa:{match.group(1)}"


def passage_from_record(record: Mapping[str, Any]) -> TrimmedPassage:
    """One line of `trimmed.jsonl` as a validated passage."""
    unknown = record.keys() - RECORD_FIELDS
    if unknown:  # keeping the record's provenance is the point, so a new field must not vanish
        raise ValueError(f"fields the Source schema does not keep: {sorted(unknown)}")
    # `words` counts the original page, so it is stored under a name that says so.
    fields = {name: value for name, value in record.items() if name != "words"}
    return TrimmedPassage(
        source_id=voa_source_id(record["url"]), original_words=record["words"], **fields
    )


def load_passages(path: Path) -> list[TrimmedPassage]:
    """Every record of `path` as a passage, or `InvalidCorpus` naming each bad line.

    A `MANIFEST.json` beside the file, when there is one, must describe exactly this file.
    """
    raw = path.read_bytes()
    problems: list[str] = []
    passages: list[TrimmedPassage] = []
    seen: set[str] = set()
    lines = raw.decode("utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        try:
            passage = passage_from_record(json.loads(line))
        except KeyError as error:
            problems.append(f"line {number}: missing field {error}")
        except ValueError as error:  # includes bad JSON and pydantic's ValidationError
            problems.append(f"line {number}: {error}")
        else:
            if passage.source_id in seen:  # two versions cannot both be current
                problems.append(f"line {number}: {passage.source_id} appears twice in the file")
            seen.add(passage.source_id)
            passages.append(passage)
    problems += _manifest_problems(path.parent / "MANIFEST.json", raw, len(lines))
    if problems:
        raise InvalidCorpus(problems)
    return passages


def _manifest_problems(manifest: Path, raw: bytes, lines: int) -> list[str]:
    if not manifest.is_file():
        return []
    expected = json.loads(manifest.read_text())
    problems = []
    if hashlib.sha256(raw).hexdigest() != expected["trimmed_jsonl_sha256"]:
        problems.append("MANIFEST.json: the file's sha256 is not the one the manifest records")
    if lines != expected["passages"]:
        problems.append(f"MANIFEST.json: {expected['passages']} passages expected, {lines} lines")
    return problems


class Outcome(StrEnum):
    INSERTED = "inserted"  # no version of the passage was stored
    SUPERSEDED = "superseded"  # another version was current; this one is now
    UNCHANGED = "unchanged"  # this version was already current
    CONFLICT = "conflict"  # this version is stored with different content


@dataclass
class IngestReport:
    inserted: int = 0
    superseded: int = 0
    unchanged: int = 0
    conflicts: list[str] = field(default_factory=list)  # keys that were refused


async def ingest_sources(passages: Sequence[TrimmedPassage], now: datetime) -> IngestReport:
    """Make each passage's version the current `Source` of that passage (ADR-0010).

    Idempotent: a version is identified by `passage.key`, so storing it again changes nothing.
    A different version of the same passage is added beside the old one, which is kept. One
    transaction per passage, so a passage never has zero or two current versions, and a run
    that stops half-way is finished by running it again. `Source` must be bound already.
    """
    client = Source.get_pymongo_collection().database.client
    report = IngestReport()
    for passage in passages:
        outcome = await run_in_transaction(client, partial(_make_current, passage, now))
        match outcome:
            case Outcome.INSERTED:
                report.inserted += 1
            case Outcome.SUPERSEDED:
                report.superseded += 1
            case Outcome.UNCHANGED:
                report.unchanged += 1
            case Outcome.CONFLICT:
                report.conflicts.append(passage.key)
    return report


async def _make_current(
    passage: TrimmedPassage, now: datetime, session: AsyncClientSession
) -> Outcome:
    collection = Source.get_pymongo_collection()
    stored = await Source.get(passage.key, session=session)
    if stored is not None:
        # The same key must mean the same content. If it does not, the trim changed without a
        # new `rules_version` (ADR-0008 5.6): refuse, and leave what is stored alone.
        if stored.model_dump(include=set(TrimmedPassage.model_fields)) != passage.model_dump():
            return Outcome.CONFLICT
        if stored.current:
            return Outcome.UNCHANGED
    # Demote before promoting: the partial unique index allows one current version at a time.
    demoted = await collection.update_many(
        {"source_id": passage.source_id, "current": True},
        {"$set": {"current": False}},
        session=session,
    )
    if stored is None:
        document = Source(id=passage.key, current=True, ingested_at=now, **passage.model_dump())
        await document.insert(session=session)
    else:  # an older version coming back, as in a rollback
        await collection.update_one(
            {"_id": passage.key}, {"$set": {"current": True}}, session=session
        )
    inserted = stored is None and demoted.modified_count == 0
    return Outcome.INSERTED if inserted else Outcome.SUPERSEDED
