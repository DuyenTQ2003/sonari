import csv
from pathlib import Path

import pytest
from voa_inventory.fetch import BASE, PoliteFetcher, Response
from voa_inventory.render import render_md
from voa_inventory.rows import COLUMNS, MIN_WORDS, load_rows, write_csv
from voa_inventory.topics import PhraseTagger, load_catalog

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


def test_failed_fetches_in_the_index_do_not_reach_the_report(cache: Path) -> None:
    def down(url: str, agent: str) -> Response:
        raise TimeoutError("timed out")

    broken = PoliteFetcher(cache, "test", 0.0, get=down, sleep=lambda _s: None)
    assert broken.fetch(f"{BASE}/a/9999.html").error == "TimeoutError"
    assert len(load_rows(cache, PhraseTagger())) == len(PAGES)


def test_rows_cover_every_cached_page_and_short_pages_are_never_usable(cache: Path) -> None:
    rows = load_rows(cache, PhraseTagger())
    assert len(rows) == len(PAGES)
    assert all(r.item.word_count < MIN_WORDS for r in rows)  # the fixtures are short ...
    assert not any(r.usable for r in rows)  # ... so the length rule rejects all of them


def test_usable_needs_licence_audio_and_length(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voa_inventory.rows.MIN_WORDS", 10)
    usable = {r.item.url.rsplit("/", 1)[1] for r in load_rows(cache, PhraseTagger()) if r.usable}
    # staff + lesson; not wire, photo, mention, no-audio or outside byline
    assert usable == {"8001.html", "8005.html"}


def test_csv_has_one_row_per_page_and_a_usable_column(
    cache: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voa_inventory.rows.MIN_WORDS", 10)
    rows = load_rows(cache, PhraseTagger())
    out = tmp_path / "out" / "inv.csv"
    write_csv(rows, out)
    with out.open(encoding="utf-8") as fh:
        read = list(csv.DictReader(fh))
    assert list(read[0]) == COLUMNS
    assert len(read) == len(PAGES)
    by = {r["url"].rsplit("/", 1)[1]: r for r in read}
    assert by["8001.html"]["usable"] == "1" and by["8001.html"]["topics"] == "food_restaurant"
    assert by["8002.html"]["usable"] == "0"
    assert by["8002.html"]["license_reasons"] == "wire_credit;third_party_media"
    assert by["8005.html"]["est_level"] == "2"
    assert {u for u, r in by.items() if r["usable"] == "1"} == {"8001.html", "8005.html"}


def test_markdown_names_topics_short_of_two_items_and_states_coverage(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voa_inventory.rows.MIN_WORDS", 10)
    rows = load_rows(cache, PhraseTagger())
    md = render_md(rows, {"sitemap_urls": 70, "seed": 3}, load_catalog(), "phrase")
    assert "**7** of them (**10.0%**)" in md
    assert "seed 3" in md and "**phrase** tagger" in md
    assert "fewer than 2 in sample" in md  # partial coverage never claims a firm SWAP
    assert "`shopping`" in md
    full = render_md(rows, {"sitemap_urls": 7, "seed": 3}, load_catalog(), "phrase")
    assert "| SWAP |" in full  # full coverage and still short: the topic must be swapped


def test_a_topic_with_enough_tags_is_never_called_confirmed(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voa_inventory.rows.MIN_WORDS", 10)
    monkeypatch.setattr("voa_inventory.render.NEEDED", 1)
    rows = load_rows(cache, PhraseTagger())
    md = render_md(rows, {"sitemap_urls": 7, "seed": 3}, load_catalog(), "phrase")
    food = next(line for line in md.splitlines() if "(`food_restaurant`)" in line)
    assert food.endswith("| 1+ tagged, unconfirmed |")  # a tag count is not a supply figure
