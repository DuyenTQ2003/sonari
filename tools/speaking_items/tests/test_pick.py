"""Which sentences are fit to practise, and how twenty are chosen. No G2P here: a stand-in
pronouncer gives each word one token, so the tests need only pyyaml."""

import random
import re
from collections import Counter
from types import SimpleNamespace
from typing import Any

import pytest
from speaking_items.pick import (
    COMMON,
    COUNT,
    PER_PASSAGE,
    QUOTA,
    Candidate,
    candidates,
    lowercase_words,
    plain,
    select,
)

VOCAB: Counter[str] = Counter(
    {w: COMMON for w in ["the", "students", "school", "teachers", "each", "learn"]}
)


def word(match: re.Match[str], source: str = "dictionary") -> Any:
    return SimpleNamespace(
        text=match.group(), start=match.start(), end=match.end(), tokens=[match.group().lower()],
        source=source,
    )  # fmt: skip


def pronounce(text: str) -> list[Any]:
    return [word(m) for m in re.finditer(r"[A-Za-z][A-Za-z'’]*", text)]


# --- what makes a sentence fit ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "The students learn in the school.",
        "I think the students learn here.",
        "Each of the students can learn.",
        "Students don’t learn in the school?",
        "Teachers say the students learn in school!",
    ],
)
def test_a_plain_sentence_is_fit(text: str) -> None:
    assert plain(text, VOCAB)


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("The students learn 3 things in school.", "a digit"),
        ("The students learn in the U.S. school.", "an abbreviation"),
        ("The students learn from Obama in school.", "a proper noun in the middle"),
        ("Obama visits the students in the school.", "a proper noun that starts it"),
        (
            "Thread helps the students learn in school.",
            "a word the corpus rarely writes lower case",
        ),
        ("NASA helps the students learn in school.", "an acronym"),
        ("The students learn (a lot) in school.", "a bracket"),
        ("The students said “learn” in school.", "a quotation mark"),
        ("The students learn: school helps them.", "a colon"),
        ("The students learn in school; teachers help.", "a semicolon"),
        (
            "They learn in the school with the students.",
            "starts with a pronoun that needs a referent",
        ),
        ("But the students learn in the school.", "starts with a connective"),
        ("The students, she says, learn in school.", "a clause that needs its speaker"),
        ("the students learn in the school.", "starts in lower case: a fragment"),
        ("The students learn in school", "no end mark"),
    ],
)
def test_an_unfit_sentence_is_refused(text: str, why: str) -> None:
    assert not plain(text, VOCAB), why


def test_a_word_is_a_proper_noun_when_the_corpus_hardly_writes_it_in_lower_case() -> None:
    vocab = lowercase_words(iter(["a thread of the school", "Thread said so", "Thread, Inc."]))
    assert vocab["thread"] == 1 and vocab["school"] == 1
    assert not plain("Thread helps the students learn in school.", vocab)


# --- cutting a passage into candidates -------------------------------------------------------


def row(lines: list[str], source: str = "1") -> dict[str, Any]:
    return {
        "id": source,
        "raw": {"text": lines, "trim": {"rules_version": "voa-trim/aaaaaaaaaaaa"}},
    }


def test_a_candidate_is_a_slice_of_its_line_and_pins_the_source_version() -> None:
    lines = ["Skip this one. The students learn in the school today. Another sentence follows it."]
    found = list(candidates(row(lines), VOCAB, pronounce))

    (c,) = found
    assert c.source == "voa:1@voa-trim/aaaaaaaaaaaa"
    assert (c.line, lines[0][c.start : c.start + len(c.text)]) == (0, c.text)
    assert c.text == "The students learn in the school today."
    assert [lines[0][c.start + w["start"] : c.start + w["end"]] for w in c.words] == c.text[
        :-1
    ].split()


def test_a_sentence_outside_the_word_window_is_not_a_candidate() -> None:
    short = "The students learn."
    long = "The students learn in the school and the teachers learn in the school too again."
    assert list(candidates(row([short, long]), VOCAB, pronounce)) == []


def test_a_sentence_with_a_guessed_pronunciation_is_not_a_candidate() -> None:
    def guess(text: str) -> list[Any]:
        return [
            word(m, "predicted" if m.group() == "school" else "dictionary")
            for m in re.finditer(r"\w+", text)
        ]

    assert list(candidates(row(["The students learn in the school today."]), VOCAB, guess)) == []


# --- choosing twenty -------------------------------------------------------------------------


def cand(
    n: int, marks: set[str], source: str = "", on_topic: bool = True, text: str = ""
) -> Candidate:
    """A ten-word sentence that shows exactly `marks`: θ and ð as words, `final s/z` as the last."""
    words = [{"text": "w", "start": 0, "end": 1, "tokens": ["w"]} for _ in range(10)]
    for i, sound in enumerate(sorted(marks - {"final s/z"})):
        words[i]["tokens"] = [sound]
    if "final s/z" in marks:
        words[-1]["tokens"] = ["w", "s"]
    return Candidate(source or f"s{n}", 0, n, text or f"Sentence {n}.", words, on_topic)


ALL = set(QUOTA)


def test_it_picks_twenty_when_there_are_more() -> None:
    assert len(select([cand(n, ALL) for n in range(60)])) == COUNT


def test_a_scarce_rule_is_filled_before_the_common_ones() -> None:
    pool = [cand(n, ALL - {"θ"}) for n in range(40)] + [cand(100 + n, {"θ"}) for n in range(8)]

    picked = select(pool)

    assert sum("θ" in c.marks for c in picked) == QUOTA["θ"]


def test_no_passage_gives_more_than_its_share() -> None:
    pool = [cand(n, ALL, source="a") for n in range(30)] + [cand(100 + n, ALL) for n in range(30)]

    per_source = Counter(c.source for c in select(pool))

    assert per_source["a"] <= PER_PASSAGE


def test_the_same_sentence_from_two_articles_is_picked_once() -> None:
    pool = [cand(n, ALL, text="Same sentence.") for n in range(5)] + [
        cand(10 + n, ALL) for n in range(30)
    ]

    assert Counter(c.text for c in select(pool))["Same sentence."] == 1


def test_a_passage_titled_for_the_unit_comes_before_one_that_is_not() -> None:
    pool = [cand(n, ALL, on_topic=False) for n in range(30)] + [
        cand(100 + n, ALL) for n in range(30)
    ]

    assert all(c.on_topic for c in select(pool))


def test_the_pick_does_not_depend_on_the_order_of_the_pool() -> None:
    pool = [
        cand(n, set(random.Random(n).sample(sorted(ALL), 3)), source=f"s{n % 15}")
        for n in range(80)
    ]
    shuffled = pool[:]
    random.Random(7).shuffle(shuffled)

    assert select(pool) == select(shuffled)


def test_a_small_pool_gives_what_there_is() -> None:
    assert len(select([cand(n, ALL) for n in range(5)])) == 5
