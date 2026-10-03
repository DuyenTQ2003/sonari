"""Bodies that are bare text in `div.wsw` / `div.wordclick`, lines separated by <br />, no <p>.

The fixtures are cached VOA pages cut to their JSON-LD block and `#article-content`:

* bare_text_wsw_2012      Technology Report, 2012: the body sits directly in div.wsw
* bare_text_wordclick_2012  a 2012 reader's letter: the body sits in div.wsw > div.wordclick
* bare_and_p_text_2012    Golden Globes, 2012: <p> paragraphs with bare paragraphs between them
* bare_text_player_2013   As It Is, 2013: a player (div.wsw__embed) inside the body container
"""

from pathlib import Path

import pytest
from voa_inventory.parse import Body, Item, parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> tuple[Item, Body]:
    return parse_page((FIXTURES / name).read_text("utf-8"), f"https://example.test/a/{name}")


def body(inner: str) -> list[str]:
    html = f'<div id="article-content"><div class="wsw">{inner}</div></div>'
    return parse_page(html, "u")[1].paragraphs


def test_2012_body_in_wsw_is_read() -> None:
    item, text = fixture("bare_text_wsw_2012.html")
    assert item.date == "2012-05-14"
    assert (item.word_count, len(text.paragraphs)) == (451, 15)
    assert text.paragraphs[0] == "This is the VOA Special English Technology Report."
    assert text.paragraphs[1].startswith("Recent developments in India and China")
    assert item.license_ok


def test_2012_body_in_wordclick_is_read() -> None:
    item, text = fixture("bare_text_wordclick_2012.html")
    assert item.date == "2012-06-04"
    assert (item.word_count, len(text.paragraphs)) == (161, 9)
    assert text.paragraphs[0].startswith("My problem is that I am afraid of people.")
    assert item.first_paragraph.startswith("My problem is that I am afraid of people.")


def test_bare_paragraphs_keep_their_place_between_p_paragraphs() -> None:
    _, text = fixture("bare_and_p_text_2012.html")

    def at(prefix: str) -> int:
        return next(i for i, p in enumerate(text.paragraphs) if p.startswith(prefix))

    assert at("George Clooney") < at("It wasn't a total loss") < at("Madonna won")
    assert at("Meryl Streep") < at("Morgan Freeman") < at("Now, on to something")
    assert len(text.paragraphs) == 16  # the 14 <p> paragraphs and the 2 bare ones


def test_player_widget_text_does_not_leak_into_the_body() -> None:
    item, text = fixture("bare_text_player_2013.html")
    assert (item.word_count, len(text.paragraphs)) == (1187, 49)
    assert text.paragraphs[1].startswith("Hello, and welcome again to As It Is.")
    joined = " ".join(text.paragraphs)
    for chrome in (
        "clipboard",
        "Embed",
        "Pop-out player",
        "Direct link",
        "0:00",
        "Voice of America",
    ):
        assert chrome not in joined


@pytest.mark.parametrize(
    "skipped",
    [
        '<div class="quiz" id="quizId">Question 1. Which word is a noun?</div>',
        '<div class="c-mmp">The code has been copied to your clipboard.</div>',
        '<div class="wsw__embed">Pop-out player</div>',
        '<div class="content-redirect">We are sorry, but this feature is not available</div>',
        "<ul><li>Write your comment in the box.</li><li>Click send.</li></ul>",
        "<table><tr><td>Stream</td><td>Download</td></tr></table>",
        "<script>var line = 'Not part of the story.';</script>",
        "<style>.line::after { content: 'Not part of the story.'; }</style>",
        "<h4>A Visit from St. Nicholas</h4>",
    ],
)
def test_widget_list_table_script_and_heading_text_is_not_read(skipped: str) -> None:
    assert body(f"Before the widget.<br />{skipped}<br />After the widget.") == [
        "Before the widget.",
        "After the widget.",
    ]


def test_br_splits_paragraphs_in_bare_text_and_joins_lines_inside_p() -> None:
    assert body("One.<br /> <br />Two.<br />Three.") == ["One.", "Two.", "Three."]
    assert body("<p>One<br />two.</p>") == ["One two."]


def test_inline_markup_stays_in_its_paragraph_and_blocks_end_it() -> None:
    assert body("It was <em>very</em> cold in <a href='/x'>Moscow</a>.") == [
        "It was very cold in Moscow."
    ]
    assert body("First line.<div>Second line.</div>Third line.") == [
        "First line.",
        "Second line.",
        "Third line.",
    ]


def test_a_line_that_is_only_a_link_or_an_mp3_download_is_not_text() -> None:
    assert body("Story.<br /><a href='/s.pdf'>Download PDF of this story</a><br />More.") == [
        "Story.",
        "More.",
    ]
    download = "Or <a href='http://x.test/a.Mp3'>download MP3</a> (Right-click and save link)"
    assert body(f"Story.<br /><small>{download}</small><br />More.") == ["Story.", "More."]
    assert body("Send an e-mail to <a href='mailto:a@b.test'>a@b.test</a>. Thanks.") == [
        "Send an e-mail to a@b.test. Thanks."
    ]


def test_text_outside_the_body_container_is_ignored() -> None:
    html = (
        '<div id="article-content"><div class="pg-title">Share this story</div>'
        '<div class="wsw">The story.</div><div class="related">Related stories</div></div>'
    )
    assert parse_page(html, "u")[1].paragraphs == ["The story."]


def test_text_after_the_container_is_ignored() -> None:
    html = '<div id="article-content"><div class="wsw">The story.</div></div>Page footer.'
    assert parse_page(html, "u")[1].paragraphs == ["The story."]


def test_a_bare_separator_line_starts_the_glossary() -> None:
    page = (
        '<div id="article-content"><div class="wsw">The story.<br />____________<br />'
        "reef - n. a line of rocks</div></div>"
    )
    parsed = parse_page(page, "u")[1]
    assert (parsed.paragraphs, parsed.glossary) == (["The story."], ["reef - n. a line of rocks"])
