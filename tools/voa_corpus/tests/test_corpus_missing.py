from pathlib import Path

import pytest
from voa_corpus import missing

SENTENCE = "The publisher of the newspaper said the editor was replaced because of her management."


def page(inner: str) -> str:
    return f'<body><div id="article-content"><div class="wsw">{inner}</div></div></body>'


def test_wilson_matches_published_values() -> None:
    lo, hi = missing.wilson(0, 40)
    assert (lo, round(hi, 4)) == (0.0, 0.0876)
    lo, hi = missing.wilson(9, 15)
    assert (round(lo, 3), round(hi, 3)) == (0.357, 0.802)
    assert missing.wilson(15, 15)[1] == 1.0


def test_draw_is_fixed_and_sorted_before_sampling() -> None:
    groups = {"zero": [f"u{i:03d}" for i in range(200)], "short": [f"s{i:03d}" for i in range(50)]}
    first = missing.draw(groups)
    shuffled = {g: list(reversed(urls)) for g, urls in groups.items()}
    assert missing.draw(shuffled) == first  # input order does not matter
    assert [len(first[g]) for g in ("zero", "short")] == [40, 15]
    assert len(set(first["zero"])) == 40
    assert missing.draw(groups, seed=1) != first


def test_text_between_br_tags_is_unread() -> None:
    assert missing.unread_words(page(f"{SENTENCE}<br /><br />{SENTENCE}<br />")) == 28


def test_paragraphs_headings_and_captions_are_read_by_the_parser_so_not_counted() -> None:
    for tag in ("p", "h2", "h3", "figcaption"):
        assert missing.unread_words(page(f"<{tag}>{SENTENCE}</{tag}>")) == 0


def test_player_quiz_list_and_link_text_is_not_counted() -> None:
    assert missing.unread_words(page(f'<div class="c-mmp">{SENTENCE}</div>')) == 0
    assert missing.unread_words(page(f'<div class="quiz">{SENTENCE}</div>')) == 0
    assert missing.unread_words(page(f"<ul><li>{SENTENCE}</li></ul>")) == 0
    assert missing.unread_words(page(f'<a href="/x">{SENTENCE}</a>')) == 0


def test_script_and_style_text_inside_the_container_is_not_counted() -> None:
    assert missing.unread_words(page(f"<script>var text = '{SENTENCE}';</script>")) == 0
    assert missing.unread_words(page(f"<style>/* {SENTENCE} */</style>")) == 0


def test_short_nodes_and_text_outside_the_container_are_not_counted() -> None:
    assert missing.unread_words(page("Share this story<br />Photo credit: Reuters")) == 0
    assert missing.unread_words(f"<body><div>{SENTENCE}</div></body>") == 0
    after = page("") + f"<footer>{SENTENCE}</footer>"
    assert missing.unread_words(after) == 0  # the container closed


def test_a_page_wide_form_does_not_hide_the_container_text() -> None:
    html = f'<form><div id="article-content"><div class="wsw">{SENTENCE}</div></div></form>'
    assert missing.unread_words(html) == 14


def test_title_key_ignores_case_and_punctuation() -> None:
    key = missing.title_key("Trump's  Plan: 'Big' Win?")
    assert key == missing.title_key("trump s plan big win")


def test_breakdown_prints_interval_and_implied_pages() -> None:
    labels = [("zero", f"u{i}", "audio-only") for i in range(40)]
    table = missing.breakdown(labels, {"zero": 27118})
    assert "| audio-only | 40/40 | 100% | 91.2%-100.0% | 27,118 |" in table
    labels = [("zero", f"u{i}", "missed-article" if i < 2 else "audio-only") for i in range(40)]
    assert "| missed-article | 2/40 | 5% |" in missing.breakdown(labels, {"zero": 100})


def test_read_labels_keeps_group_url_label(tmp_path: Path) -> None:
    path = tmp_path / "labels.tsv"
    path.write_text("group\turl\tlabel\tevidence\nzero\tu1\taudio-only\tplayer\n", "utf-8")
    assert missing.read_labels(path) == [("zero", "u1", "audio-only")]


@pytest.mark.parametrize("n", [1, 15, 40, 1000])
def test_wilson_interval_contains_the_proportion(n: int) -> None:
    for k in (0, n // 3, n):
        lo, hi = missing.wilson(k, n)
        assert lo <= k / n <= hi
