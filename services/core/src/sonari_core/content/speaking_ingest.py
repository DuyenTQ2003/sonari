"""Reading the items file and storing the items: the part of speaking items that needs `ingest`."""

import json
from datetime import datetime
from pathlib import Path

from sonari_core.content.ingest import IngestReport, InvalidCorpus, Outcome
from sonari_core.content.models import Source
from sonari_core.content.speaking import SpeakingItem, SpeakingItemRecord


def load_items(path: Path) -> list[SpeakingItemRecord]:
    """Every line of `path` as a record, or `InvalidCorpus` naming each bad line."""
    items: list[SpeakingItemRecord] = []
    problems: list[str] = []
    for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1):
        try:
            item = SpeakingItemRecord.model_validate(json.loads(line))
        except ValueError as error:  # bad JSON and pydantic's ValidationError
            problems.append(f"line {number}: {error}")
            continue
        if any(item.key == other.key for other in items):
            problems.append(f"line {number}: {item.key} appears twice")
        items.append(item)
    if problems:
        raise InvalidCorpus(problems)
    return items


async def source_problems(items: list[SpeakingItemRecord]) -> list[str]:
    """Items whose pinned Source is not stored, or does not hold the sentence unchanged there."""
    problems = []
    for item in items:
        source = await Source.get(item.source)
        if source is None:
            problems.append(f"{item.key}: {item.source} is not in content.sources")
            continue
        found = source.text[item.line] if item.line < len(source.text) else ""
        if found[item.start : item.start + len(item.text)] != item.text:
            problems.append(f"{item.key}: the sentence is not in {item.source}, line {item.line}")
    return problems


async def ingest_items(items: list[SpeakingItemRecord], now: datetime) -> IngestReport:
    """Store each item under its key. The same key with the same content is left alone; the same
    key with other content is a conflict and is refused."""
    report = IngestReport()
    for item in items:
        stored = await SpeakingItem.get(item.key)
        if stored is None:
            outcome = Outcome.INSERTED
            await SpeakingItem(id=item.key, ingested_at=now, **item.model_dump()).insert()
        elif stored.model_dump(include=set(SpeakingItemRecord.model_fields)) != item.model_dump():
            outcome = Outcome.CONFLICT
        else:
            outcome = Outcome.UNCHANGED
        report.record(outcome, item.key)
    return report
