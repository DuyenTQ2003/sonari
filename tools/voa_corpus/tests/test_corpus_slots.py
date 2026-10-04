"""Slots of the closed lists: names in a row, programme titles, report topics (ADR-0008 5.3)."""

import pytest
from voa_corpus.boilerplate import classify, normalise


@pytest.mark.parametrize(
    ("sentence", "form"),
    [
        (
            "Jill Robbins and Anna Matteo wrote this lesson for Learning English.",
            "<p> wrote this lesson for learning english",
        ),
        ("Nancy Steinbach, Paul Thompson and Caty Weaver", "<p>"),
        ("Anna Matteo met Caty Weaver at noon", "<p> met <p> at noon"),  # not a list of names
        (
            "Check out our website for more episodes of Words and Their Stories.",
            "check out our website for more episodes of <prog>",
        ),
        ("Welcome to Words to the Wise!", "welcome to <prog>"),
        ("This Agriculture Report was written by Gary Garriott.", "this <rep> was written by <p>"),
        ("This is the VOA Special English Health Report.", "this is the <rep>"),
    ],
)
def test_a_closed_list_entry_is_one_slot(sentence: str, form: str) -> None:
    assert normalise(sentence) == form


@pytest.mark.parametrize(
    "line",
    [
        "Jill Robbins and Anna Matteo wrote this lesson for Learning English.",
        "Welcome to Words to the Wise!",
        "Anna Matteo will be here tomorrow with another edition of Words and Their Stories.",
        "This Agriculture Report was written by Gary Garriott.",
    ],
)
def test_a_line_made_of_slots_and_listed_words_is_frame(line: str) -> None:
    hit = classify(line)
    assert hit and hit[1] == len(line.split())


@pytest.mark.parametrize(
    "line",
    [
        "My deadline for Words and Their Stories is every Thursday.",
        "Anna Matteo and Caty Weaver went to the market to buy fruit.",
        "He said the health report was wrong.",
    ],
)
def test_a_slot_does_not_make_a_sentence_somebody_wrote_into_frame(line: str) -> None:
    hit = classify(line)
    assert not (hit and hit[1] >= len(line.split()))


@pytest.mark.parametrize(
    "line",
    [
        "And that\u2019s \u201cWords and Their Stories.\u201d",
        'And that\'s "Words and Their Stories."',
        "And that\u2019s \u201cWords and Their Stories\u201d",
    ],
)
def test_a_title_in_double_quotes_is_the_same_slot_as_the_bare_title(line: str) -> None:
    assert normalise(line) == "and that's <prog>"
    hit = classify(line)
    assert hit and hit[1] == len(line.split())


def test_double_quotes_are_not_part_of_the_form_a_sentence_is_listed_in() -> None:
    assert normalise('He said "I\u2019m Anna".') == normalise("He said I'm Anna.")


def test_quoted_speech_around_a_sign_off_is_still_not_a_whole_listed_sentence() -> None:
    line = '"I\'m Anna Matteo," she said.'
    hit = classify(line)
    assert not (hit and hit[1] >= len(line.split()))
