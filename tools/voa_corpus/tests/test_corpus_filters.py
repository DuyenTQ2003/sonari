import pytest
from voa_corpus.filters import (
    COVERAGE_EDGES,
    FK_EDGES,
    LENGTH_EDGES,
    MAX_FK,
    MAX_WORDS,
    MIN_WORDS,
    Passage,
    blockers,
    bucket,
)


def passage(**changes: object) -> Passage:
    """A passage that passes every check, then changed as the test needs."""
    fields: dict[str, object] = {
        "words": 500, "fk": 6.0, "licence_ok": True, "boiler": {"furniture": 4},
    }  # fmt: skip
    return Passage("https://example.org/a/1.html", **{**fields, **changes})  # type: ignore[arg-type]


def test_a_passage_that_meets_every_threshold_has_no_blockers() -> None:
    assert blockers(passage()) == []


@pytest.mark.parametrize(
    ("words", "blocked"),
    [
        (99, True),
        (MIN_WORDS - 1, True),
        (MIN_WORDS, False),
        (MAX_WORDS, False),
        (MAX_WORDS + 1, True),
    ],
)
def test_the_length_window_is_inclusive_at_both_ends(words: int, blocked: bool) -> None:
    assert ("length" in blockers(passage(words=words))) is blocked


@pytest.mark.parametrize(
    ("fk", "blocked"),
    [(0.0, False), (MAX_FK - 0.01, False), (MAX_FK, True), (9.5, True), (None, True)],
)
def test_the_grade_must_be_below_the_ceiling_and_known(fk: float | None, blocked: bool) -> None:
    assert ("readability" in blockers(passage(fk=fk))) is blocked


def test_one_line_of_editorial_boilerplate_blocks_a_passage_that_must_be_used_as_is() -> None:
    assert blockers(passage(boiler={"presenter": 3})) == ["boilerplate"]


def test_page_furniture_is_not_editorial_boilerplate() -> None:
    assert blockers(passage(boiler={"furniture": 40})) == []


def test_a_tolerance_lets_a_little_boilerplate_through_and_no_more() -> None:
    few, many = passage(boiler={"script": 25}), passage(boiler={"script": 26})  # 5.0% and 5.2%
    assert blockers(few, cut_share=0.05) == []
    assert blockers(many, cut_share=0.05) == ["boilerplate"]


def test_frame_words_on_a_line_that_stays_can_never_be_cut() -> None:
    """A label before speech, or a sign-off glued to content, stays in the text (ADR-0008)."""
    stays = passage(boiler={"script": 2}, kept=2)
    assert blockers(stays, cut_share=0.05) == ["boilerplate"]
    assert blockers(stays, cut_share=1.0) == ["boilerplate"]


def test_only_words_on_lines_that_can_go_count_against_the_cut() -> None:
    mixed = passage(boiler={"presenter": 20, "script": 2}, kept=2)  # 20 words can go, 2 stay
    assert mixed.removable == 20
    assert blockers(passage(boiler={"presenter": 20}), cut_share=0.05) == []  # 4% of 500
    assert blockers(mixed, cut_share=0.05) == ["boilerplate"]  # the 2 that stay still block


def test_length_is_measured_on_the_text_that_is_left_after_the_cut() -> None:
    short = passage(words=MIN_WORDS + 5, boiler={"presenter": 10})  # 255 words, 245 after the cut
    assert "length" in blockers(short, cut_share=0.05)
    assert "length" not in blockers(short)  # as is nothing is cut
    long = passage(words=MAX_WORDS + 10, boiler={"presenter": 12})  # 1,210 words, 1,198 after
    assert blockers(long, cut_share=0.05) == []
    assert "length" in blockers(long)


def test_a_passage_without_the_licence_is_blocked() -> None:
    assert blockers(passage(licence_ok=False)) == ["licence"]


def test_a_stub_or_a_copy_is_not_a_passage() -> None:
    assert "not a passage" in blockers(passage(words=60))
    assert "not a passage" in blockers(passage(duplicate=True))


def test_blockers_come_in_the_order_of_the_funnel() -> None:
    bad = passage(words=2000, fk=9.0, boiler={"script": 50}, licence_ok=False)
    assert blockers(bad) == ["length", "readability", "boilerplate", "licence"]


def test_other_thresholds_can_be_passed_in() -> None:
    p = passage(words=1500, fk=8.5)
    assert blockers(p) == ["length", "readability"]
    assert blockers(p, words=(250, 2000), max_fk=9.0) == []


def test_editorial_words_leave_out_furniture() -> None:
    assert passage(boiler={"furniture": 9, "script": 2, "programme": 5}).editorial_words == 7


def test_coverage_is_the_share_of_non_proper_tokens_at_a1_to_b2() -> None:
    vocab = (50, 20, 20, 5, 1, 0, 4, 100)  # A1..C2, unlisted, proper nouns (not counted)
    assert passage(vocab=vocab).coverage == pytest.approx(95 / 100)
    assert passage().coverage is None


@pytest.mark.parametrize(
    ("value", "edges", "label"),
    [
        (4.99, FK_EDGES, "<5"),
        (5, FK_EDGES, "5-7"),
        (6.99, FK_EDGES, "5-7"),
        (7, FK_EDGES, "7-9"),
        (13, FK_EDGES, ">=13"),
        (99, FK_EDGES, ">=13"),
        (0, LENGTH_EDGES, "<1"),
        (99, LENGTH_EDGES, "1-100"),
        (100, LENGTH_EDGES, "100-250"),
        (1200, LENGTH_EDGES, "1200-2000"),
        (0.949, COVERAGE_EDGES, "0.9-0.95"),
        (0.95, COVERAGE_EDGES, "0.95-0.98"),
    ],
)
def test_buckets_are_half_open_and_open_ended(
    value: float, edges: tuple[float, ...], label: str
) -> None:
    assert bucket(value, edges) == label
