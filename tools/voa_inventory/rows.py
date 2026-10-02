"""Inventory rows: parse the cache, tag, and count.

`Row.usable` is the only definition of a usable item, and `count_usable` the only place
that turns rows into per-topic counts, so no table can count a page that failed the
licence filter, has no audio, or is too short.
"""

import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from voa_inventory.crawl import ARTICLE
from voa_inventory.fetch import PoliteFetcher
from voa_inventory.levels import estimate_level
from voa_inventory.parse import Item, parse_item
from voa_inventory.topics import Tags

MIN_WORDS = 100  # shorter pages are captions, video stubs or menus, not source passages
LEVEL_4 = 4
COLUMNS = [
    "url", "title", "program", "date", "byline", "has_audio", "audio_url", "word_count",
    "avg_sentence_len", "fk_grade", "est_level", "usable", "topics", "candidate_topics",
    "license_ok", "license_reasons", "credit_line",
]  # fmt: skip


class Tagger(Protocol):
    name: str
    tags_only_usable: bool

    def tag_all(self, pairs: Sequence[tuple[str, str]]) -> list[Tags]: ...


@dataclass
class Row:
    item: Item
    level: int | None
    topics: dict[str, float] = field(default_factory=dict)
    candidate_topics: dict[str, float] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        i = self.item
        return i.license_ok and i.has_audio and i.word_count >= MIN_WORDS


@dataclass(frozen=True)
class Counts:
    level4: int
    levels45: int
    any_level: int


def count_usable(
    rows: Sequence[Row], topic_id: str, candidate: bool = False
) -> tuple[Counts, list[Row]]:
    """Counts of usable rows tagged `topic_id`, and those rows (level 4 first)."""
    key = "candidate_topics" if candidate else "topics"
    pool = [r for r in rows if r.usable and topic_id in getattr(r, key)]
    pool.sort(key=lambda r: r.level != LEVEL_4)
    counts = Counts(
        level4=sum(r.level == LEVEL_4 for r in pool),
        levels45=sum(r.level in (4, 5) for r in pool),
        any_level=len(pool),
    )
    return counts, pool


def load_rows(cache_dir: Path, tagger: Tagger) -> list[Row]:
    fetcher = PoliteFetcher(cache_dir, "offline")
    urls = set()
    for line in (cache_dir / "index.jsonl").read_text("utf-8").splitlines():
        entry = json.loads(line)
        if entry["status"] == 200 and ARTICLE.match(entry["url"]):
            urls.add(entry["url"])
    rows = []
    for url in sorted(urls):
        body = fetcher.cached(url)
        if body:
            item = parse_item(body.decode("utf-8", "replace"), url)
            rows.append(Row(item, estimate_level(item.program, item.fk_grade)))
    todo = [r for r in rows if r.usable or not tagger.tags_only_usable]
    for row, tags in zip(
        todo, tagger.tag_all([(r.item.title, r.item.first_paragraph) for r in todo]), strict=True
    ):
        row.topics, row.candidate_topics = tags.topics, tags.candidates
    return rows


def write_csv(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for r in rows:
            i = r.item
            writer.writerow([
                i.url, i.title, i.program, i.date, i.byline, int(i.has_audio), i.audio_url,
                i.word_count, i.avg_sentence_len, "" if i.fk_grade is None else i.fk_grade,
                "" if r.level is None else r.level, int(r.usable), ";".join(sorted(r.topics)),
                ";".join(sorted(r.candidate_topics)), int(i.license_ok),
                ";".join(i.license_reasons), i.credit_line[:200],
            ])  # fmt: skip
