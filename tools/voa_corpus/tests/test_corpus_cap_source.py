"""The cap of ADR-0008 decision 2 has one source in the tools: `filters.DEFAULT_CAP`.

The report's "up to 5% cut" column once carried its own `0.05`, so changing the constant would
have moved the corpus writer and left the report counting passages at a cap nobody writes.
"""

import pytest
from voa_corpus import analyze, filters, write_trimmed
from voa_corpus.filters import Passage


def seven_percent_cut() -> Passage:
    """A passage a 5% cap refuses and an 8% cap accepts (35 of 500 words are frame)."""
    page = Passage(
        "https://learningenglish.voanews.com/a/1.html",
        words=500,
        text_words=465,
        fk=5.0,
        licence_ok=True,
        units=(0,),
    )
    page.boiler = {"presenter": 35}
    return page


def cap_column(table: str) -> tuple[str, str]:
    """The header and the first unit's count of the column that follows 'as is'."""
    header, _, first_unit = table.splitlines()[:3]
    heads = [cell.strip() for cell in header.strip("|").split("|")]
    counts = [cell.strip() for cell in first_unit.strip("|").split("|")]
    return heads[3], counts[3]


def test_the_writer_and_the_filters_share_the_one_cap() -> None:
    assert write_trimmed.DEFAULT_CAP is filters.DEFAULT_CAP


def test_the_report_counts_the_cap_column_at_the_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at_5 = analyze.topics([seven_percent_cut()], [])
    monkeypatch.setattr(filters, "DEFAULT_CAP", 0.08)
    at_8 = analyze.topics([seven_percent_cut()], [])

    assert cap_column(at_5) == ("up to 5% cut", "0")
    assert cap_column(at_8) == ("up to 8% cut", "1")
