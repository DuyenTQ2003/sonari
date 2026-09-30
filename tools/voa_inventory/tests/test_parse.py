from pathlib import Path

import pytest
from voa_inventory.levels import estimate_level, stats, syllables
from voa_inventory.parse import Item, parse_item

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Item:
    return parse_item((FIXTURES / name).read_text("utf-8"), f"https://example.test/a/{name}")


def test_staff_article_is_extracted_and_accepted() -> None:
    item = load("staff_article.html")
    assert item.title == "Eating at Home or in a Restaurant"
    assert item.program == "Words and Their Stories"
    assert item.date == "2025-03-15"
    assert item.byline == "VOA Learning English"
    assert item.has_audio
    assert item.audio_url == "https://voa-audio.example/vle/2025/03/11/a.mp3"
    assert item.credit_line == "Ana Lopez wrote this story for VOA Learning English."
    assert item.first_paragraph.startswith("Many people like to eat breakfast at home.")
    assert item.license_ok
    assert item.license_reasons == ()


def test_word_count_skips_credit_glossary_and_page_chrome() -> None:
    item = load("staff_article.html")
    # 3 body paragraphs + "I'm Ana Lopez."; not the credit, glossary, nav or script text.
    assert item.word_count == 22 + 22 + 15 + 3


def test_wire_credit_and_third_party_photo_exclude_the_item() -> None:
    item = load("wire_article.html")
    assert not item.license_ok
    assert item.license_reasons == ("wire_credit", "third_party_media")
    assert item.byline == "VOA Learning English"  # the byline metadata alone would pass


def test_wire_mention_in_the_body_excludes_the_item() -> None:
    item = load("wire_mention_article.html")
    assert item.license_reasons == ("wire_mention",)
    assert not item.license_ok


def test_photo_credit_alone_excludes_the_item_and_is_reported_separately() -> None:
    item = load("photo_credit_article.html")
    assert item.license_reasons == ("third_party_media",)
    assert not item.license_ok


def test_byline_outside_voa_staff_is_rejected() -> None:
    item = load("outside_byline_article.html")
    assert item.license_reasons == ("byline_not_staff",)


def test_page_without_audio() -> None:
    item = load("no_audio_article.html")
    assert not item.has_audio
    assert item.audio_url == ""
    assert item.license_ok


def test_lesson_program_is_unescaped_and_carries_the_level() -> None:
    item = load("lesson_article.html")
    assert item.program == "Let's Learn English - Level 2"
    assert estimate_level(item.program, item.fk_grade) == 2


def test_page_without_article_container_yields_an_empty_record() -> None:
    item = parse_item("<html><title>x</title><body><p>hello</p></body></html>", "u")
    assert item.word_count == 0
    assert not item.has_audio
    assert item.byline == ""
    assert not item.license_ok  # unknown byline


@pytest.mark.parametrize(
    ("word", "count"),
    [("cat", 1), ("water", 2), ("make", 1), ("table", 2), ("beautiful", 3), ("the", 1)],
)
def test_syllable_heuristic(word: str, count: int) -> None:
    assert syllables(word) == count


def test_stats_on_a_known_text() -> None:
    words, per_sentence, fk = stats(["The cat sat. The dog ran home."])
    assert words == 7
    assert per_sentence == 3.5
    assert fk is not None
    assert -3 < fk < 3  # very short words and sentences


def test_single_sentence_has_no_grade() -> None:
    assert stats(["Only one sentence here."])[2] is None


@pytest.mark.parametrize(
    ("grade", "level"), [(4.0, 4), (6.99, 4), (7.0, 5), (8.9, 5), (10.9, 6), (14.0, 7)]
)
def test_fk_bands(grade: float, level: int) -> None:
    assert estimate_level("As It Is", grade) == level


def test_level_is_unknown_without_a_grade_or_lesson_level() -> None:
    assert estimate_level("As It Is", None) is None


def test_media_page_without_article_container_keeps_programme_date_and_audio() -> None:
    item = load("media_page.html")
    assert item.program == "As It Is"
    assert item.date == "2020-02-05"
    assert item.title == "Learning English Broadcast"
    assert item.has_audio
    assert item.word_count == 0
    assert not item.license_ok  # no byline on the page: unverifiable, so excluded
    assert item.license_reasons == ("byline_not_staff",)
