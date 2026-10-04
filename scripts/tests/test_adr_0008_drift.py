"""Guard: ADR-0008's rules are written down in more than one place, and nothing else compares them.

The tools write the trimmed corpus and the content service reads it, and the service cannot
import the tools (ADR-0010), so every rule exists twice. This file covers the line invariant and
the record's shape; `test_adr_0008_constraints_drift.py` covers the numbers (cap, window, grade).

* "A trim removes whole lines and nothing else" (decision 1): `voa_corpus.trim.validate` and
  `TrimmedPassage`. Both get the same cases here and must give the same verdict.
* The record the writer emits is the one the service keeps (decision 3).
* The cap, the length window and the grade ceiling (decision 2) are pinned to the ADR's own
  text, so changing one takes a superseding ADR and a deliberate edit of this file.

Runs under `make test-scripts`, which installs pydantic and beanie for the service's models.
"""

import re
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

import pytest
from adr_0008_fakes import Parts, service_accepts, tools_accepts, valid
from sonari_core.content.models import RemovedLine, Trim, TrimmedPassage
from voa_corpus import filters
from voa_corpus.filters import DEFAULT_CAP
from voa_corpus.trim import Removed
from voa_corpus.write_trimmed import make_record
from voa_inventory.levels import stats

ROOT = Path(__file__).resolve().parents[2]
ADR_0008 = ROOT / "docs" / "adr" / "0008-boilerplate-trimming-removes-whole-lines-only.md"


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
    p[1].pop()  # the kept "Share" at index 5, which no removed record covers


def kept_lines_reordered(p: Parts) -> None:
    p[1].reverse()


def removed_line_also_kept(p: Parts) -> None:
    p[1].insert(0, "I'm June Simms.")


def removed_text_is_not_the_original_line(p: Parts) -> None:
    p[2][1]["text"] = "Something VOA never wrote."


def a_line_removed_twice(p: Parts) -> None:
    p[2].append(dict(p[2][1]))


def an_index_past_the_end(p: Parts) -> None:
    p[2][1]["index"] = len(p[0])


def a_negative_index(p: Parts) -> None:
    p[2][1]["index"] = -1


def a_removed_line_without_a_kind(p: Parts) -> None:
    p[2][1]["kind"] = ""


def a_removed_line_without_a_rule(p: Parts) -> None:
    p[2][1]["rule"] = ""


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

    words = stats(parts[1])[0]  # a case must not be refused for its length instead
    assert filters.MIN_WORDS <= words <= filters.MAX_WORDS, f"{mutate.__name__} left the window"
    assert (tools_accepts(*parts), service_accepts(*parts)) == (accepted, accepted)


def test_the_removed_record_has_the_same_fields_in_both() -> None:
    assert {f.name for f in fields(Removed)} == set(RemovedLine.model_fields)


def test_the_writer_emits_a_record_the_service_accepts_and_keeps_whole() -> None:
    body = [f"Sentence {number} of the passage is short." for number in range(60)]
    paragraphs = ["Share", "I'm June Simms.", *body]
    meta = {
        "url": "https://learningenglish.voanews.com/a/1.html",
        "title": "A passage",
        "program": "",
        "fk": 4.1,
        "words": stats(paragraphs)[0],  # what the parser reports as the page's word count
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
