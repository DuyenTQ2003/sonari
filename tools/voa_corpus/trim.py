"""The trim of ADR-0008: whole lines only, with what is needed to audit it and undo it.

One function does the trimming. `make voa-corpus` counts what it removes and `write_trimmed.py`
stores it, so the report counts what ingestion would produce. A trim never edits a word inside a
line, never reorders and never inserts: `kept` is the original lines minus `removed`, and
`validate` checks exactly that, so a stored trim can be audited line by line.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from voa_corpus.boilerplate import HERE, Hit, explain_all


@dataclass(frozen=True)
class Removed:
    """One removed line: its 0-based index in the original, the rule's kind and id, the line."""

    index: int
    kind: str
    rule: str
    text: str


@dataclass
class Trim:
    hits: list[Hit | None]  # for every original line: what the classifier made of it
    kept: list[str]
    removed: list[Removed]

    @property
    def removed_words(self) -> int:
        """Editorial words on the lines removed: what counts against the cap. Page furniture is
        removed and recorded like any line, but it is layout and does not count."""
        return sum(len(r.text.split()) for r in self.removed if r.kind != "furniture")

    @property
    def kept_frame_words(self) -> int:
        """Frame words on a line that stays whole (a speaker label before speech, a sign-off glued
        to content). A trim cannot cut them, so they block "as is" and every cap."""
        gone = {r.index for r in self.removed}
        return sum(
            h[1] for i, h in enumerate(self.hits) if h and h[0] != "furniture" and i not in gone
        )


def trim(paragraphs: list[str]) -> Trim:
    """Remove every line that is wholly frame (a hit that covers all of its words)."""
    hits = explain_all(paragraphs)
    removed = [
        Removed(i, hit[0], hit[2], p)
        for i, (p, hit) in enumerate(zip(paragraphs, hits, strict=True))
        if hit and hit[1] >= len(p.split())
    ]
    gone = {r.index for r in removed}
    kept = [p for i, p in enumerate(paragraphs) if i not in gone]
    return Trim(hits, kept, removed)


def validate(original: Sequence[str], kept: Sequence[str], removed: Sequence[Removed]) -> list[str]:
    """Why a stored trim cannot be trusted; empty when it can. The kept lines must be the original
    lines minus the removed indexes, byte for byte and in order, and each removed record must
    be the line it says it is."""
    problems = []
    indexes = [r.index for r in removed]
    if len(set(indexes)) != len(indexes):
        problems.append("a line is recorded as removed twice")
    for r in removed:
        if not 0 <= r.index < len(original):
            problems.append(f"removed index {r.index} is outside the original")
        elif original[r.index] != r.text:
            problems.append(f"removed line {r.index} is not the original line")
        if not (r.kind and r.rule):
            problems.append(f"removed line {r.index} has no kind or rule")
    gone = set(indexes)
    if list(kept) != [p for i, p in enumerate(original) if i not in gone]:
        problems.append("kept lines are not the original lines minus the removed ones")
    return problems


def rules_files() -> list[Path]:
    """Everything that decides what is frame: the lists, the patterns and the classifier."""
    return [*sorted((HERE / "frames").glob("*")), HERE / "boilerplate.tsv", HERE / "boilerplate.py"]


def rules_version(files: Sequence[Path] | None = None) -> str:
    """`trim.rules_version` (ADR-0008 decision 3 and 5.6): a digest of the files that decide, so
    any change to a list, a pattern or the classifier is a new version."""
    digest = hashlib.sha256()
    for path in files if files is not None else rules_files():
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return f"voa-trim/{digest.hexdigest()[:12]}"
