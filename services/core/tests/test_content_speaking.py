"""Speaking items as validated records. No database: what a bad file must be refused for."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from sonari_core.content.ingest import InvalidCorpus
from sonari_core.content.speaking import MAX_WORDS, MIN_WORDS, SpeakingItemRecord
from sonari_core.content.speaking_ingest import load_items

ITEMS = Path(__file__).resolve().parents[3] / "tools" / "speaking_items" / "items.jsonl"
TEXT = "The students read the short test sentence daily."


def make_item(
    text: str = TEXT, source: str = "voa:990000001@voa-trim/aaaaaaaaaaaa"
) -> dict[str, Any]:
    words = [
        {"text": m.group(), "start": m.start(), "end": m.end(), "tokens": [m.group().lower()]}
        for m in re.finditer(r"[A-Za-z']+", text)
    ]
    return {
        "source": source, "line": 4, "start": 0, "unit": "Study and work", "text": text,
        "words": words, "g2p_version": "g2p/test",
    }  # fmt: skip


def write(tmp_path: Path, *items: dict[str, Any] | str) -> Path:
    path = tmp_path / "items.jsonl"
    path.write_text("".join((i if isinstance(i, str) else json.dumps(i)) + "\n" for i in items))
    return path


def test_an_item_is_found_again_by_its_source_line_and_offset() -> None:
    item = SpeakingItemRecord.model_validate(make_item())

    assert item.key == "voa:990000001@voa-trim/aaaaaaaaaaaa#4:0"


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("The students read.", "fewer than the minimum words"),
        (" ".join(["word"] * (MAX_WORDS + 1)) + ".", "more than the maximum words"),
        ("The students read 3 short test sentences.", "a digit"),
    ],
)
def test_an_item_outside_the_criteria_is_refused(text: str, why: str) -> None:
    with pytest.raises(ValueError):
        SpeakingItemRecord.model_validate(make_item(text))
    assert MIN_WORDS <= len(TEXT.split()) <= MAX_WORDS, why


def test_a_word_that_is_not_where_it_says_is_refused() -> None:
    item = make_item()
    item["words"][2]["start"] += 1

    with pytest.raises(ValueError, match="is not at"):
        SpeakingItemRecord.model_validate(item)


def test_a_word_without_phonemes_is_refused() -> None:
    item = make_item()
    item["words"][0]["tokens"] = []

    with pytest.raises(ValueError):
        SpeakingItemRecord.model_validate(item)


def test_load_names_every_bad_line_and_refuses_the_file_whole(tmp_path: Path) -> None:
    short = make_item("Too short.")
    path = write(tmp_path, make_item(), short, "not json", make_item())

    with pytest.raises(InvalidCorpus) as error:
        load_items(path)

    problems = "\n".join(error.value.problems)
    assert "line 2" in problems and "line 3" in problems
    assert "line 4: voa:990000001@voa-trim/aaaaaaaaaaaa#4:0 appears twice" in problems


def test_the_committed_items_are_valid_and_pin_one_stored_version_each() -> None:
    items = load_items(ITEMS)

    assert len(items) == 20
    assert {i.unit for i in items} == {"Study and work"}
    assert all(re.fullmatch(r"voa:\d+@voa-trim/[0-9a-f]{12}", i.source) for i in items)
    assert len({i.text for i in items}) == 20  # VOA published some articles twice
    assert len({i.g2p_version for i in items}) == 1
