"""One function does the trimming (ADR-0008 decision 3): whole lines only, with provenance."""

import re
from pathlib import Path

from voa_corpus.boilerplate import explain
from voa_corpus.trim import Removed, rules_version, trim, validate

PASSAGE = [
    "Share",  # page furniture
    "VOICE ONE: I'm Bryan Lynn.",  # a label and a sign-off: all frame
    "Rice is grown in many countries.",
    'MIKE LIZOTTE: "If you want that bulb to survive, dig it out."',  # speech behind a label
    "I'm Anna Matteo.",
    "Wheat is grown in colder places.",
]


def test_what_is_kept_is_the_original_minus_the_removed_lines_untouched() -> None:
    t = trim(PASSAGE)
    gone = {r.index for r in t.removed}
    assert gone == {0, 1, 4}
    assert t.kept == [p for i, p in enumerate(PASSAGE) if i not in gone]


def test_every_removed_line_is_recorded_with_its_index_kind_rule_and_text() -> None:
    t = trim(PASSAGE)
    assert [(r.index, r.kind, r.text) for r in t.removed] == [
        (0, "furniture", "Share"),
        (1, "presenter", "VOICE ONE: I'm Bryan Lynn."),
        (4, "presenter", "I'm Anna Matteo."),
    ]
    assert all(r.rule for r in t.removed)


def test_a_label_in_front_of_speech_keeps_the_line_whole_and_still_counts_as_frame() -> None:
    t = trim(PASSAGE)
    assert PASSAGE[3] in t.kept
    assert t.kept_frame_words == 2  # "MIKE LIZOTTE:" cannot be cut out of the speech


def test_removed_words_exclude_furniture() -> None:
    t = trim(PASSAGE)
    assert t.removed_words == len(PASSAGE[1].split()) + len(PASSAGE[4].split())


def test_a_passage_with_no_frame_is_returned_whole() -> None:
    t = trim(["Rice is grown in many countries.", "Wheat is grown in colder places."])
    assert t.removed == []
    assert t.kept == ["Rice is grown in many countries.", "Wheat is grown in colder places."]


def test_an_empty_passage_trims_to_nothing() -> None:
    t = trim([])
    assert (t.kept, t.removed, t.removed_words, t.kept_frame_words) == ([], [], 0, 0)


def test_a_valid_trim_passes_validation() -> None:
    t = trim(PASSAGE)
    assert validate(PASSAGE, t.kept, t.removed) == []


def test_validation_catches_an_edited_kept_line() -> None:
    t = trim(PASSAGE)
    edited = [*t.kept[:-1], t.kept[-1].replace("Wheat", "Maize")]
    assert validate(PASSAGE, edited, t.removed)


def test_validation_catches_a_line_that_was_dropped_without_a_record() -> None:
    t = trim(PASSAGE)
    assert validate(PASSAGE, t.kept[1:], t.removed)


def test_validation_catches_a_removed_record_that_does_not_match_the_original() -> None:
    t = trim(PASSAGE)
    forged = [Removed(r.index, r.kind, r.rule, r.text + "!") for r in t.removed]
    assert validate(PASSAGE, t.kept, forged)


def test_validation_catches_a_reordered_kept_list() -> None:
    t = trim(PASSAGE)
    assert validate(PASSAGE, t.kept[::-1], t.removed)


def test_explain_names_the_rule_that_decided_a_line() -> None:
    kind, words, rule = explain("I'm Anna Matteo.") or ("", 0, "")
    assert (kind, words) == ("presenter", 3)
    assert rule.startswith("list:")


def test_the_rules_version_names_the_files_it_was_computed_from() -> None:
    version = rules_version()
    assert re.fullmatch(r"voa-trim/[0-9a-f]{12}", version)
    assert version == rules_version()


def test_the_rules_version_changes_when_a_list_changes(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\n")
    before = rules_version([tmp_path / "a.txt"])
    (tmp_path / "a.txt").write_text("one\ntwo\n")
    assert rules_version([tmp_path / "a.txt"]) != before
