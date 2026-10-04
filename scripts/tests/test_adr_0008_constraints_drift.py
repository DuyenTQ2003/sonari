"""Guard: the numbers ADR-0008 fixes (decision 2) are enforced twice, and the two must agree.

The tools choose the passages (`filters.blockers`) and the content service refuses a record that
breaks the rules (`TrimmedPassage`). The service cannot import the tools (ADR-0010), so it carries
its own constants, its own word counter and its own derivation of the cut. Each of them is
compared here with the tools' version: the same number, the same edges, the same count.

The one place the two differ on purpose: a grade of NaN. The tools never produce one, so
`blockers` has no rule for it, and the service refuses it because `nan < 7` is false.
"""

import pytest
from adr_0008_fakes import service_accepts, valid
from sonari_core.content import trim_rules
from voa_corpus import filters
from voa_corpus.filters import DEFAULT_CAP, Passage
from voa_corpus.trim import Removed
from voa_corpus.trim import Trim as ToolsTrim
from voa_inventory.levels import stats

URL = "https://learningenglish.voanews.com/a/1.html"


def one_line(words: int, word: str = "word") -> list[str]:
    return [" ".join([word] * words)]


def test_the_service_pins_the_same_numbers_as_the_tools() -> None:
    service = (trim_rules.TRIM_CAP, trim_rules.MIN_WORDS, trim_rules.MAX_WORDS, trim_rules.MAX_FK)

    assert service == (DEFAULT_CAP, filters.MIN_WORDS, filters.MAX_WORDS, filters.MAX_FK)


@pytest.mark.parametrize(
    ("kept", "allowed"), [(249, False), (250, True), (1200, True), (1201, False)]
)
def test_the_length_window_has_the_same_edges_in_both(kept: int, allowed: bool) -> None:
    page = Passage(URL, words=kept, text_words=kept, fk=4.0, licence_ok=True)

    picked = "length" not in filters.blockers(page, cut_share=DEFAULT_CAP)
    accepted = service_accepts(one_line(kept), one_line(kept), [])

    assert (picked, accepted) == (allowed, allowed)


@pytest.mark.parametrize(
    ("fk", "allowed"), [(6.99, True), (7.0, False), (7.01, False), (None, False)]
)
def test_the_grade_ceiling_is_exclusive_in_both(fk: float | None, allowed: bool) -> None:
    page = Passage(URL, words=300, text_words=300, fk=fk, licence_ok=True)

    picked = "readability" not in filters.blockers(page, cut_share=DEFAULT_CAP)
    accepted = service_accepts(*valid(), fk=fk)  # type: ignore[arg-type]  # None is the case

    assert (picked, accepted) == (allowed, allowed)


@pytest.mark.parametrize(("removed_words", "allowed"), [(50, True), (51, False)])
def test_the_cap_is_inclusive_in_both_places(removed_words: int, allowed: bool) -> None:
    words = 1000
    cut, body = one_line(removed_words, "alpha"), one_line(words - removed_words, "beta")
    removed = [{"index": 0, "kind": "presenter", "rule": "list:presenter.txt", "text": cut[0]}]
    page = Passage(URL, words=words, text_words=words - removed_words, fk=4.0, licence_ok=True)
    page.boiler = {"presenter": removed_words}

    picked = "boilerplate" not in filters.blockers(page, cut_share=DEFAULT_CAP)
    accepted = service_accepts([*cut, *body], body, removed)

    assert (picked, accepted) == (allowed, allowed)


TEXTS = [
    "Plain words only.",
    "It's well-known that don’t and can't differ.",
    "In 2020, 1,000 people - the U.S. team - met.",
    "e-mail address: a.b@c.org and x2y",
    chr(0xDC) + "n" + chr(0xEF) + "code caf" + chr(0xE9) + " na" + chr(0xEF) + "ve",  # accents
    "-leading dash, trailing- dash- and 'quoted' words",
    "3.14 42 !!! ... ---",
    "",
]


@pytest.mark.parametrize("text", TEXTS)
def test_the_service_counts_words_as_the_corpus_does(text: str) -> None:
    assert trim_rules.count_words([text]) == stats([text])[0]


def test_the_service_counts_a_passage_as_the_corpus_does() -> None:
    assert trim_rules.count_words(TEXTS) == stats(TEXTS)[0]


def test_the_service_counts_the_words_cut_as_the_tools_do() -> None:
    lines = [
        Removed(0, "furniture", "furniture", "Share this page now"),  # layout: does not count
        Removed(1, "presenter", "list:presenter.txt", "I'm June Simms, with a  double  space."),
        Removed(2, "programme", "list:programme.txt", "1,000 well-known words\tand a tab"),
    ]
    in_the_tools = ToolsTrim([], [], lines).removed_words

    in_the_service = trim_rules.editorial_words((line.kind, line.text) for line in lines)

    assert in_the_service == in_the_tools
