"""ADR-0008 as the content service enforces it where data enters the system. No database here.

A file that names its own cap, its own word counts and its own grade is not trusted: the cap is
5%, the trimmed text is 250-1,200 words and below grade 7 (decision 2), and the numbers a trim
declares about itself are derived from the lines it lists (decisions 1 and 2). Each refusal names
the decision it comes from, so whoever reads the error can find the rule.
"""

from typing import Any

import pytest

from sonari_core.content.models import TrimmedPassage

Record = dict[str, Any]

CUT = "alpha"  # the words of a removed line and of a kept line differ, so a miscount shows
KEPT = "beta"


def build(
    *,
    kept: int = 290,
    removed: int = 10,
    furniture: bool = False,
    fk: float = 4.2,
    cap: float = 0.05,
) -> Record:
    """A trimmed passage as the writer would emit it: `removed` words cut from a line, `kept`
    words in the text, every declared number consistent with the lines. The defaults cut 3.3%
    (10 of 300 words), comfortably inside the cap, so a test about something else is not also a
    test of the cap's edge."""
    cut_line = " ".join([CUT] * removed)
    kept_line = " ".join([KEPT] * kept)
    original = ([cut_line] if removed else []) + [kept_line] + (["Share"] if furniture else [])
    cut = (
        [{"index": 0, "kind": "presenter", "rule": "list:presenter.txt", "text": cut_line}]
        if removed
        else []
    )
    if furniture:
        last = len(original) - 1
        cut.append({"index": last, "kind": "furniture", "rule": "furniture", "text": "Share"})
    words = removed + kept + (1 if furniture else 0)  # the corpus counts every line it parsed
    return {
        "url": "https://learningenglish.voanews.com/a/990000001.html",
        "title": "A passage",
        "program": "",
        "fk": fk,
        "words": words,
        "original_text": original,
        "text": [kept_line],
        "trim": {
            "rules_version": "voa-trim/aaaaaaaaaaaa",
            "cap": cap,
            "removed_words": removed,  # furniture is layout and does not count
            "removed_share": round(removed / words, 4) if words else 0.0,
            "removed": cut,
        },
    }


def passage(record: Record) -> TrimmedPassage:
    rest = {name: value for name, value in record.items() if name != "words"}
    return TrimmedPassage(source_id="voa:990000001", original_words=record["words"], **rest)


def refuses(record: Record, decision: str) -> None:
    with pytest.raises(ValueError, match=rf"ADR-0008 decision {decision}"):
        passage(record)


def test_a_cut_of_exactly_the_cap_is_accepted() -> None:
    assert passage(build(removed=15, kept=285)).trim.removed_words == 15  # 15 of 300 is 5.00%


@pytest.mark.parametrize(("removed", "kept"), [(30, 270), (6, 294)], ids=["10% cut", "2% cut"])
def test_a_file_that_declares_a_bigger_cap_is_refused_whatever_it_cut(
    removed: int, kept: int
) -> None:
    # Declared inside its own 20%. Even a cut that stays within 5% does not make the 20% true:
    # `trim.cap` must be the ADR's 5% (decision 2), and a bigger one is a file trimmed another way.
    refuses(build(removed=removed, kept=kept, cap=0.2), "2")


def test_a_cut_over_the_cap_is_refused() -> None:
    refuses(build(removed=16, kept=284), "2")  # 5.33%


def test_a_declared_cut_smaller_than_the_one_made_is_refused() -> None:
    record = build(removed=30, kept=270)  # really 10%
    record["trim"]["removed_words"] = 15
    record["trim"]["removed_share"] = 0.05

    refuses(record, "2")


def test_a_declared_share_that_is_not_the_derived_one_is_refused() -> None:
    record = build()
    record["trim"]["removed_share"] = 0.01

    refuses(record, "2")


def test_a_declared_word_count_that_is_not_the_derived_one_is_refused() -> None:
    record = build()
    record["trim"]["removed_words"] = 9

    refuses(record, "2")


def test_page_furniture_does_not_count_toward_the_cap() -> None:
    assert passage(build(furniture=True)).trim.removed_words == 10


def test_a_furniture_word_counted_toward_the_cap_is_refused() -> None:
    record = build(furniture=True)
    record["trim"]["removed_words"] = 11

    refuses(record, "2")


def test_the_original_word_count_is_derived_so_it_cannot_hide_a_big_cut() -> None:
    record = build(removed=100, kept=200)  # really a 33% cut
    record["words"] = 10_000  # a denominator no line supports, to make the cut look small
    record["trim"]["removed_share"] = round(100 / 10_000, 4)

    refuses(record, "2")


def test_a_stored_original_word_count_that_no_line_supports_is_refused() -> None:
    record = build()  # every other number is right, and the cut is inside the cap
    record["words"] = 10_000

    refuses(record, "2")


def test_a_passage_with_no_words_is_refused_and_does_not_divide_by_zero() -> None:
    with pytest.raises(ValueError, match="ADR-0008"):
        passage(build(removed=0, kept=0))


@pytest.mark.parametrize(
    ("kept", "accepted"), [(249, False), (250, True), (1200, True), (1201, False)]
)
def test_the_trimmed_text_is_250_to_1200_words(kept: int, accepted: bool) -> None:
    record = build(removed=0, kept=kept)

    if accepted:
        assert passage(record).text == record["text"]
    else:
        refuses(record, "2")


def test_the_window_is_judged_on_the_trimmed_text_not_the_original() -> None:
    # 1,230 words on the page, 1,200 left once 30 words are cut: inside the window, and a 2.4% cut.
    assert passage(build(removed=30, kept=1200)).text


@pytest.mark.parametrize(
    ("fk", "accepted"),
    [(6.99, True), (-1.0, True), (7.0, False), (7.5, False), (float("nan"), False)],
)
def test_the_grade_is_below_7(fk: float, accepted: bool) -> None:
    record = build(fk=fk)

    if accepted:
        assert passage(record).fk == fk
    else:
        refuses(record, "2")
