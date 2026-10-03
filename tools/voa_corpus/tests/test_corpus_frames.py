"""The closed lists behind the boilerplate classifier must stay what ADR-0008 section 5 requires."""

import re
from collections import Counter

from voa_corpus import boilerplate
from voa_corpus.boilerplate import FRAME_FILES, HERE, fold, normalise, sentences

FRAMES_DIR = HERE / "frames"


def entries(name: str) -> list[str]:
    return boilerplate._data_lines(FRAMES_DIR / name)


def test_every_listed_sentence_is_in_the_form_the_classifier_looks_up() -> None:
    """A line that normalise() would rewrite can never match, so it must not be in a list."""
    stale = [
        (name, line) for name, _ in FRAME_FILES for line in entries(name) if normalise(line) != line
    ]
    assert stale == []


def test_no_sentence_is_listed_twice() -> None:
    counts = Counter(line for name, _ in FRAME_FILES for line in entries(name))
    assert [line for line, n in counts.items() if n > 1] == []


def test_staff_are_full_names_without_duplicates() -> None:
    names = [fold(n) for n in entries("staff.txt")]
    assert [n for n in names if len(n.split()) < 2] == []
    assert [n for n, c in Counter(names).items() if c > 1] == []


def test_a_name_is_a_slot_only_where_the_list_puts_one() -> None:
    assert normalise("I'm Bryan Lynn.") == "i'm <p>"
    assert normalise("I’m Bryan Lynn") == "i'm <p>"
    assert normalise("I'm Vietnamese.") == "i'm vietnamese"
    assert normalise("Bryan Lynnette") == "bryan lynnette"  # a name inside a longer word is not one


def test_every_pattern_rule_is_anchored_at_both_ends() -> None:
    """ADR-0008 5.3: nothing may match a substring of a line."""
    rules = [
        line.split("\t")[2]
        for line in (HERE / "boilerplate.tsv").read_text("utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert rules
    assert [rx for rx in rules if not (rx.startswith("^") and rx.endswith("$"))] == []
    assert all(re.compile(rx).groups >= 0 for rx in rules)


def test_a_data_file_stays_under_300_lines() -> None:
    files = [FRAMES_DIR / name for name, _ in FRAME_FILES] + [FRAMES_DIR / "staff.txt"]
    assert [f.name for f in files if len(f.read_text("utf-8").splitlines()) > 300] == []


def test_dr_and_jr_do_not_end_a_sentence_inside_a_name() -> None:
    assert sentences("And I'm Dr. Jill Robbins.") == ["And I'm Dr. Jill Robbins."]
    assert sentences("I'm Mario Ritter, Jr. And I'm Pete Musto.") == [
        "I'm Mario Ritter, Jr.",
        "And I'm Pete Musto.",
    ]


def test_a_fused_separator_does_not_hide_a_sentence() -> None:
    assert sentences("We want to hear from you. ____________") == ["We want to hear from you."]


def test_a_sentence_does_not_end_before_a_lower_case_word() -> None:
    assert sentences("Mario Ritter, Jr. was the editor.") == ["Mario Ritter, Jr. was the editor."]
    assert boilerplate.classify("Mario Ritter, Jr. was the editor.") == ("programme", 6)
