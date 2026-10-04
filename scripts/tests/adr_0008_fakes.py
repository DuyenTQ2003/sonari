"""Shared cases for the drift tests of ADR-0008: one trim, in the shapes both sides read.

The tools and the content service each judge a trim. These helpers build the same trim for both,
with every number the file declares about itself taken from the tools (`levels.stats` for the
original's words, `Trim.removed_words` for the cut), the way the writer would emit them.
"""

from typing import Any

from pydantic import ValidationError
from sonari_core.content.models import RemovedLine, Trim, TrimmedPassage
from voa_corpus.filters import DEFAULT_CAP
from voa_corpus.trim import Removed, validate
from voa_corpus.trim import Trim as ToolsTrim
from voa_inventory.levels import stats

# Two identical furniture lines: the one at index 0 is removed and the one at index 5 is kept, so
# a verdict that went by text instead of by index would be wrong. The long line keeps the kept
# text inside the length window (267 words), so a case that damages a line cannot also be refused
# for its length: the window is the subject of another test.
LONG = " ".join(["word"] * 260)
ORIGINAL = ["Share", "Kept line one.", LONG, "I'm June Simms.", "Kept line two.", "Share"]
REMOVED = [
    {"index": 0, "kind": "furniture", "rule": "furniture", "text": "Share"},
    {"index": 3, "kind": "presenter", "rule": "list:presenter.txt", "text": "I'm June Simms."},
]
KEPT = ["Kept line one.", LONG, "Kept line two.", "Share"]

Parts = tuple[list[str], list[str], list[dict[str, Any]]]  # original, kept, removed


def valid() -> Parts:
    return list(ORIGINAL), list(KEPT), [dict(line) for line in REMOVED]


def tools_accepts(original: list[str], kept: list[str], removed: list[dict[str, Any]]) -> bool:
    return validate(original, kept, [Removed(**line) for line in removed]) == []


def service_passage(
    original: list[str],
    kept: list[str],
    removed: list[dict[str, Any]],
    *,
    fk: float = 4.0,
    cap: float = DEFAULT_CAP,
) -> TrimmedPassage:
    """The passage with the numbers the writer would declare for these lines."""
    removed_words = ToolsTrim([], kept, [Removed(**line) for line in removed]).removed_words
    original_words = stats(original)[0]
    return TrimmedPassage(
        source_id="voa:1",
        url="https://learningenglish.voanews.com/a/1.html",
        title="A passage",
        fk=fk,
        original_words=original_words,
        original_text=original,
        text=kept,
        trim=Trim(
            rules_version="voa-trim/aaaaaaaaaaaa",
            cap=cap,
            removed_words=removed_words,
            removed_share=round(removed_words / original_words, 4) if original_words else 0.0,
            removed=[RemovedLine(**line) for line in removed],
        ),
    )


def service_accepts(*parts: Any, **options: float) -> bool:
    try:
        service_passage(*parts, **options)
    except ValidationError:
        return False
    return True
