import csv
from pathlib import Path

import pytest
from voa_inventory.fetch import BASE, PoliteFetcher, Response
from voa_inventory.report import COLUMNS, MIN_WORDS, load_rows, render_md, write_csv
from voa_inventory.topics import load_candidates, load_topics

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = {
    "staff_article.html": 8001,
    "wire_article.html": 8002,
    "photo_credit_article.html": 8003,
    "wire_mention_article.html": 8004,
    "lesson_article.html": 8005,
    "no_audio_article.html": 8006,
    "outside_byline_article.html": 8007,
}


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    def get(url: str, agent: str) -> Response:
        if url.endswith("/robots.txt"):
            return Response(200, b"")  # allow everything
        name = next(n for n, i in PAGES.items() if url.endswith(f"/a/{i}.html"))
        return Response(200, (FIXTURES / name).read_bytes())

    fetcher = PoliteFetcher(tmp_path, "test", 0.0, get=get, sleep=lambda _s: None)
    for i in PAGES.values():
        fetcher.get(f"{BASE}/a/{i}.html")
    return tmp_path


def test_rows_cover_every_cached_page_and_short_pages_are_never_usable(cache: Path) -> None:
    rows = load_rows(cache, load_topics(), load_candidates())
    assert len(rows) == len(PAGES)
    assert all(r.item.word_count < MIN_WORDS for r in rows)  # the fixtures are short ...
    assert not any(r.usable for r in rows)  # ... so the length rule rejects all of them


def test_usable_needs_licence_audio_and_length(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voa_inventory.report.MIN_WORDS", 10)
    rows = load_rows(cache, load_topics(), load_candidates())
    usable = {r.item.url.rsplit("/", 1)[1] for r in rows if r.usable}
    assert usable == {
        "8001.html",
        "8005.html",
    }  # staff + lesson; not wire/photo/mention/no-audio/byline


def test_csv_has_one_row_per_page_with_the_documented_columns(cache: Path, tmp_path: Path) -> None:
    rows = load_rows(cache, load_topics(), load_candidates())
    out = tmp_path / "out" / "inv.csv"
    write_csv(rows, out)
    with out.open(encoding="utf-8") as fh:
        read = list(csv.DictReader(fh))
    assert list(read[0]) == COLUMNS
    assert len(read) == len(PAGES)
    staff = next(r for r in read if r["url"].endswith("8001.html"))
    assert staff["license_ok"] == "1" and staff["has_audio"] == "1"
    assert staff["topics"] == "food_restaurant"
    assert staff["candidate_topics"] == "housing_home"
    wire = next(r for r in read if r["url"].endswith("8002.html"))
    assert wire["license_reasons"] == "wire_credit;third_party_media"
    lesson = next(r for r in read if r["url"].endswith("8005.html"))
    assert lesson["est_level"] == "2"


def test_markdown_names_topics_short_of_two_items_and_states_coverage(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voa_inventory.report.MIN_WORDS", 10)
    rows = load_rows(cache, load_topics(), load_candidates())
    md = render_md(rows, {"sitemap_urls": 70, "seed": 3}, load_topics(), load_candidates())
    assert "**7** of them (**10.0%**)" in md
    assert "seed 3" in md
    assert "fewer than 2 in sample" in md  # partial coverage never claims a firm SWAP
    assert "`shopping`" in md
    assert "| Home and housing (`housing_home`) | 1 | 1 | 1 |" in md  # candidates are tagged too
    full = render_md(rows, {"sitemap_urls": 7, "seed": 3}, load_topics(), load_candidates())
    assert "| SWAP |" in full  # full coverage and still short: the topic must be swapped
