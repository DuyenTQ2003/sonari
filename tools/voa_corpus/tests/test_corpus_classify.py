"""The type and safety tags: which rule decides, and the false matches the stems were fixed for."""

import json
from pathlib import Path

import pytest
from voa_corpus.classify import (
    SAFETY,
    TEACHING,
    USABLE_TYPES,
    classify_type,
    safety_flags,
    safety_hits,
)  # fmt: skip
from voa_corpus.filters import LESSONS_OR_FICTION

PROSE = ["Rice is grown in many countries.", "It needs a lot of water to grow."]
REPORTED = ["The mayor said the park will open.", "Officials told reporters it cost a lot."]
DIALOGUE = [f"{name}: Hello, how are you today?" for name in ("Anna", "Marsha") * 4]


def kind(title: str = "A Title", program: str = "", lines: list[str] = PROSE) -> str:
    return classify_type(title, program, lines)[0]


@pytest.mark.parametrize(
    ("title", "program", "lines", "expected"),
    [
        ("VOA English Newscast: 1600 UTC October 20, 2015", "", REPORTED, "newscast"),
        ('Woman, 26, Vietnam: "My husband is cheating on me"', "", PROSE, "advice_column"),
        (
            "Lesson 7: What Are You Doing?",
            "Let's Learn English - Level 1",
            DIALOGUE,
            "dialogue_script",
        ),
        ("Chicken Little", "American Stories", PROSE, "fiction"),
        ("VOA Staff Presents 'A Visit From St. Nicholas'", "As It Is", PROSE, "fiction"),
        ("Adjective Clauses", "Everyday Grammar", PROSE, "english_teaching"),
        ("Words and Their Stories: Grapevine", "", PROSE, "english_teaching"),
        ("Improve Your Pronunciation", "Education Tips", PROSE, "english_teaching"),
        ("Present Tense Regular Verbs", "", ["LESSON 2", *PROSE], "english_teaching"),
        ("American Mosaic: Women Kept Guitars Strumming", "", PROSE, "magazine"),
        ("DC Dinosaur Hunter; New Family Movies; Albums", "", PROSE, "magazine"),
        ("Mayor Opens Park", "", REPORTED, "news_item"),
        ("How Rice Grows", "", PROSE, "explainer"),
    ],
)
def test_each_type_is_decided_by_its_own_rule(title, program, lines, expected) -> None:
    assert kind(title, program, lines) == expected


def test_a_lesson_programme_with_speaker_labels_is_teaching_not_a_dialogue_script() -> None:
    assert kind("Doctors and Nurses", "Words and Their Stories", DIALOGUE) == "english_teaching"


def test_a_lesson_programme_without_speaker_labels_is_not_a_dialogue_script() -> None:
    assert (
        kind("Review of Lessons 2-24", "Let's Learn English - Level 1", PROSE) == "english_teaching"
    )


def test_a_story_about_a_teacher_in_an_education_programme_is_not_an_english_lesson() -> None:
    assert kind("A Blind Teacher's Vision", "Education", REPORTED) == "news_item"


def test_a_news_programme_needs_less_reported_speech_to_count_as_news() -> None:
    lines = [
        "Rice grows in wet fields.",
        *["It grows well."] * 100,
        "The farmer said so.",
    ]  # 0.3 per 100
    assert kind("Rice", "", lines) == "explainer"
    assert kind("Rice", "As It Is", lines) == "news_item"


def test_advice_to_the_reader_is_an_explainer_even_when_it_quotes_an_expert() -> None:
    lines = ["Experts say you should sleep well.", "You need eight hours of sleep, they said."]
    assert kind("Sleep", "", lines) == "explainer"


def test_a_list_article_with_headings_is_an_explainer_even_with_reported_speech() -> None:
    lines = ["Apps", "Maps", "Notes", "The company said it is free.", "Officials said so."]
    assert kind("Apps", "", lines) == "explainer"


def test_only_explainer_and_news_item_can_carry_a_lesson() -> None:
    assert USABLE_TYPES == ("explainer", "news_item")


def flags(title: str = "", lead: str = "", body: str = "", min_body: int = 0) -> frozenset[str]:
    """The module's own threshold, unless a test asks for another."""
    hits = safety_hits(title, lead, [body])
    return safety_flags(hits, min_body) if min_body else safety_flags(hits)


def test_a_stem_in_the_title_or_lead_flags_the_category_at_once() -> None:
    assert flags(lead="The army said it would leave.") == {"war"}


# "Tornado Season!" in miniature: storms that only damaged homes, and an average, not a toll.
EXPLAINED = (
    "Tornadoes damaged hundreds of homes. Tornadoes kill 70 people in an average year. "
    "Most injuries happen when objects hit people."
)
CYCLONE = (
    "The cyclone hit in March, killing more than 800 people. Many are missing. Survivors wait."
)
TRIMMED = Path.home() / "sonari-trimmed/voa/trimmed.jsonl"


def test_a_phenomenon_explained_is_not_a_disaster_but_one_reported_with_casualties_is() -> None:
    body = EXPLAINED + " Tornadoes form in storms." * 3  # "tornado" recurs, "kill" does not
    assert not flags(title="Tornado Season!", lead="Storms damaged hundreds of homes.", body=body)
    assert "disaster" in flags(title="Cyclone Idai Hits", body=CYCLONE)
    assert not flags(
        title="Floodwaters Threaten a House", body="The flood rose. The house is empty."
    )
    assert not flags(
        title="Drought", body="The drought was long. His animals died."
    )  # one is not two


@pytest.mark.skipif(not TRIMMED.exists(), reason="the trimmed corpus is outside the repo")
def test_tornado_season_in_the_corpus_is_not_flagged() -> None:
    row = next(r for r in map(json.loads, TRIMMED.open()) if r["url"].endswith("/181598.html"))
    assert not safety_flags(safety_hits(row["title"], row["text"][0], row["text"]))


@pytest.mark.parametrize(
    ("text", "category", "flagged"),
    [
        ("Congress made the park. ", "politics", False),
        ("An advertising campaign began. ", "politics", False),
        ("The presidential campaign ended. ", "politics", True),
        ("Democrats and Republicans argued. ", "politics", True),
        ("A trade war began. ", "war", False),
        ("I saw Star Wars. ", "war", False),
        ("A home invasion happened. ", "war", False),
        ("A fight, a battle for supremacy. ", "war", False),
        ("The civil war went on. ", "war", True),
        ("The photo shoot ended. ", "crime", False),
        ("The shooting happened. ", "crime", True),
        ("A heart attack, a panic attack. ", "crime", False),
        ("The attack hurt people. ", "crime", True),
        ("A gangrene infection. ", "crime", False),
        ("Mia stole the show. ", "crime", False),
        ("Peaceful non-violence won. ", "crime", False),
        ("Park Gun-ha and Guns ‘n’ Roses played. ", "crime", False),  # noqa: RUF001
        ("Armed guns were seen. ", "crime", True),
        ("The police came. ", "crime", True),
        ("A tornado outbreak and altitude sickness. ", "disease", False),
        ("The outbreak spread. ", "disease", True),
    ],
)
def test_a_stem_catches_its_topic_and_not_the_other_senses_of_its_word(
    text, category, flagged
) -> None:
    assert (category in flags(body=text * 3)) is flagged  # three mentions: a theme


def test_a_phrase_that_two_disease_stems_match_counts_once() -> None:
    phrase = "The coronavirus pandemic began. "
    assert "disease" not in flags(body=phrase * 2)
    assert "disease" in flags(body=phrase * 3)


def test_a_stem_in_the_body_flags_only_when_it_recurs() -> None:
    assert not flags(body="A war story.") and not flags(body="War and war.")
    assert flags(body="War, war and war.") == {"war"}
    assert flags(body="War and war.", min_body=2) == {"war"}


def test_grammar_sentences_trumpets_and_the_verb_aids_are_not_flagged() -> None:
    body = "A sentence is a sentence. He played the trumpet. This aids digestion."
    assert not flags(title=body, body=body * 5)


def test_the_disease_AIDS_is_flagged_by_its_capitals() -> None:
    assert flags(title="AIDS Researcher Killed") >= {"disease"}


def test_every_category_has_stems_and_a_lesson_programme_is_not_a_flagged_topic() -> None:
    assert set(SAFETY) == {"war", "politics", "disaster", "disease", "crime", "death"}
    assert not flags(title="Everyday Grammar: Gerunds and Infinitives")


def test_the_teaching_programmes_cover_the_filters_lesson_list_except_fiction() -> None:
    assert set(LESSONS_OR_FICTION) - set(TEACHING) == {"American Stories"}
