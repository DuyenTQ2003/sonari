"""Guard: ADR-0008's rules are written down in more than one place, and nothing else compares them.

The tools write the trimmed corpus and the content service reads it, and the service cannot
import the tools (ADR-0010), so some rules exist twice:

* "A trim removes whole lines and nothing else": `voa_corpus.trim.validate` and
  `TrimmedPassage`. Both get the same cases here and must give the same verdict.
* The record the writer emits is the one the service keeps (ADR-0008 decision 3).
* The cut is within the cap: `filters.blockers` picks the passages, and `TrimmedPassage`
  refuses a record that cut more than its own `cap`. Both must agree on the boundary.

The cap, the length window and the grade ceiling (ADR-0008 decision 2) exist in the tools only:
the service stores `fk` and `cap` but pins no number, and stores no word count of `text`
(ADR-0010), so it cannot apply the window. They are pinned here to the ADR's own text, so
changing one takes a superseding ADR and a deliberate edit of this file.

Runs under `make test-scripts`, which installs pydantic and beanie for the service's models.
"""

import re
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sonari_core.content.models import RemovedLine, Trim, TrimmedPassage
from voa_corpus import filters
from voa_corpus.filters import Passage
from voa_corpus.trim import Removed, validate
from voa_corpus.write_trimmed import DEFAULT_CAP, make_record

ROOT = Path(__file__).resolve().parents[2]
ADR_0008 = ROOT / "docs" / "adr" / "0008-boilerplate-trimming-removes-whole-lines-only.md"

# Two identical furniture lines: the one at index 0 is removed and the one at index 4 is kept, so
# a verdict that went by text instead of by index would be wrong.
ORIGINAL = ["Share", "Kept line one.", "I'm June Simms.", "Kept line two.", "Share"]
REMOVED = [
    {"index": 0, "kind": "furniture", "rule": "furniture", "text": "Share"},
    {"index": 2, "kind": "presenter", "rule": "list:presenter.txt", "text": "I'm June Simms."},
]
KEPT = ["Kept line one.", "Kept line two.", "Share"]

Parts = tuple[list[str], list[str], list[dict[str, Any]]]  # original, kept, removed


def tools_accepts(original: list[str], kept: list[str], removed: list[dict[str, Any]]) -> bool:
    return validate(original, kept, [Removed(**line) for line in removed]) == []


def service_passage(
    original: list[str],
    kept: list[str],
    removed: list[dict[str, Any]],
    cap: float = 1.0,
    share: float = 0.0,
) -> TrimmedPassage:
    return TrimmedPassage(
        source_id="voa:1",
        url="https://learningenglish.voanews.com/a/1.html",
        title="A passage",
        fk=4.0,
        original_words=100,
        original_text=original,
        text=kept,
        trim=Trim(
            rules_version="voa-trim/aaaaaaaaaaaa",
            cap=cap,
            removed_words=0,
            removed_share=share,
            removed=[RemovedLine(**line) for line in removed],
        ),
    )


def service_accepts(*parts: Any, **cut: float) -> bool:
    try:
        service_passage(*parts, **cut)
    except ValidationError:
        return False
    return True


def valid() -> Parts:
    return list(ORIGINAL), list(KEPT), [dict(line) for line in REMOVED]


def nothing_removed(p: Parts) -> None:
    p[1][:] = p[0]
    p[2].clear()


def removed_listed_out_of_order(p: Parts) -> None:
    p[2].reverse()


def kept_line_edited(p: Parts) -> None:
    p[1][0] += "!"


def kept_line_dropped_without_a_record(p: Parts) -> None:
    p[1].pop(0)


def the_wrong_one_of_two_identical_lines_dropped(p: Parts) -> None:
    p[1].pop()  # the kept "Share" at index 4, which no removed record covers


def kept_lines_reordered(p: Parts) -> None:
    p[1].reverse()


def removed_line_also_kept(p: Parts) -> None:
    p[1].insert(0, "I'm June Simms.")


def removed_text_is_not_the_original_line(p: Parts) -> None:
    p[2][0]["text"] = "Something VOA never wrote."


def a_line_removed_twice(p: Parts) -> None:
    p[2].append(dict(p[2][0]))


def an_index_past_the_end(p: Parts) -> None:
    p[2][0]["index"] = len(p[0])


def a_negative_index(p: Parts) -> None:
    p[2][0]["index"] = -1


def a_removed_line_without_a_kind(p: Parts) -> None:
    p[2][0]["kind"] = ""


def a_removed_line_without_a_rule(p: Parts) -> None:
    p[2][0]["rule"] = ""


ACCEPTED = [nothing_removed, removed_listed_out_of_order]
REFUSED = [
    kept_line_edited,
    kept_line_dropped_without_a_record,
    the_wrong_one_of_two_identical_lines_dropped,
    kept_lines_reordered,
    removed_line_also_kept,
    removed_text_is_not_the_original_line,
    a_line_removed_twice,
    an_index_past_the_end,
    a_negative_index,
    a_removed_line_without_a_kind,
    a_removed_line_without_a_rule,
]


def test_the_base_case_is_a_valid_trim_for_both() -> None:
    assert (tools_accepts(*valid()), service_accepts(*valid())) == (True, True)


@pytest.mark.parametrize(
    ("mutate", "accepted"),
    [pytest.param(m, True, id=m.__name__) for m in ACCEPTED]
    + [pytest.param(m, False, id=m.__name__) for m in REFUSED],
)
def test_both_validators_give_the_verdict_adr_0008_asks_for(
    mutate: Callable[[Parts], None], accepted: bool
) -> None:
    parts = valid()
    mutate(parts)

    assert (tools_accepts(*parts), service_accepts(*parts)) == (accepted, accepted)


def test_the_removed_record_has_the_same_fields_in_both() -> None:
    assert {f.name for f in fields(Removed)} == set(RemovedLine.model_fields)


def test_the_writer_emits_a_record_the_service_accepts_and_keeps_whole() -> None:
    body = [f"Sentence {number} of the passage is short." for number in range(20)]
    paragraphs = ["Share", "I'm June Simms.", *body]
    meta = {
        "url": "https://learningenglish.voanews.com/a/1.html",
        "title": "A passage",
        "program": "",
        "fk": 4.1,
        "words": 3 + 8 * len(body),  # editorial words of the original, furniture excluded
    }

    record = make_record(meta, paragraphs, DEFAULT_CAP)

    assert record["trim"]["removed"], "the real rules removed nothing: the test proves nothing"
    # The service renames `words` to `original_words` (ADR-0010) and derives `source_id`.
    renamed = {"original_words": "words"}
    service_fields = {renamed.get(name, name) for name in TrimmedPassage.model_fields}
    assert set(record) == service_fields - {"source_id"}
    assert set(record["trim"]) == set(Trim.model_fields)
    assert all(set(line) == set(RemovedLine.model_fields) for line in record["trim"]["removed"])
    rest = {name: value for name, value in record.items() if name != "words"}
    passage = TrimmedPassage(source_id="voa:1", original_words=record["words"], **rest)
    assert passage.text == record["text"]


@pytest.mark.parametrize(("removed_words", "allowed"), [(50, True), (51, False)])
def test_the_cap_is_inclusive_in_both_places(removed_words: int, allowed: bool) -> None:
    words = 1000
    page = Passage("https://learningenglish.voanews.com/a/1.html", words=words)
    page.boiler = {"presenter": removed_words}

    picked = "boilerplate" not in filters.blockers(page, cut_share=DEFAULT_CAP)
    kept = service_accepts(*valid(), cap=DEFAULT_CAP, share=removed_words / words)

    assert (picked, kept) == (allowed, allowed)


def adr_0008(pattern: str, what: str) -> tuple[str, ...]:
    found = re.search(pattern, ADR_0008.read_text(encoding="utf-8"))
    if found is None:
        pytest.fail(
            f"{ADR_0008.name} no longer states {what} in the form this test reads. "
            "If a superseding ADR changed it, update the code and this test together."
        )
    return found.groups()


def test_the_cap_is_the_one_adr_0008_fixes() -> None:
    (percent,) = adr_0008(r"The cap is (\d+(?:\.\d+)?)% of the passage's words", "the cap")

    assert float(percent) / 100 == DEFAULT_CAP


def test_the_length_window_and_grade_ceiling_are_the_ones_adr_0008_fixes() -> None:
    low, high, grade = adr_0008(  # the ADR is wrapped, so a phrase can break across lines
        r"length window\s+\((\d[\d,]*)-(\d[\d,]*)\s+words\)\s+and\s+the\s+grade\s+ceiling\s+"
        r"\(Flesch-Kincaid\s+below\s+(\d+(?:\.\d+)?)\)",
        "the length window and the grade ceiling",
    )

    in_the_adr = (int(low.replace(",", "")), int(high.replace(",", "")), float(grade))

    assert in_the_adr == (filters.MIN_WORDS, filters.MAX_WORDS, filters.MAX_FK)
