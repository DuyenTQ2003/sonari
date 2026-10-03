import pytest
from voa_corpus.boilerplate import classify


@pytest.mark.parametrize(
    "text",
    [
        "No media source currently available",
        "Share",
        "Follow us",
        "Print",
        "Or Download MP3 (Right-click or option-click and save link)",
        "___",
    ],
)
def test_page_furniture(text: str) -> None:
    assert classify(text) == ("furniture", len(text.split()))


def test_a_paragraph_of_invisible_characters_is_furniture() -> None:
    assert classify("\u200b\u00ad") == ("furniture", 0)


@pytest.mark.parametrize(
    "text", ["VOICE ONE:", "Voice 2", "HOST:", "Barbara Klein:", "(MUSIC)", "((theme))"]
)
def test_script_scaffolding(text: str) -> None:
    kind, _ = classify(text) or ("", 0)
    assert kind == "script"


@pytest.mark.parametrize(
    "text",
    [
        "I’m Bryan Lynn.",
        "And I'm Caty Weaver.",
        "I’m Mario Ritter, Jr.",
        "I’m ­Pete Musto.",
        "This is Steve Ember with the VOA Special English Education Report.",
        "I'm Doug Johnson. I hope you enjoyed our program today.",
    ],
)
def test_the_presenters_introducing_and_signing_off(text: str) -> None:
    kind, words = classify(text) or ("", 0)
    assert kind in ("presenter", "programme")
    assert words == len(text.replace("­", "").split())


@pytest.mark.parametrize(
    "text",
    [
        "This is the VOA Special English Health Report.",
        "And that’s What’s Trending Today.",
        "From Washington, this is VOA News.",
        "Faith Pirlo wrote this lesson for VOA Learning English.",
        "Join us again next week for another EXPLORATIONS program on the Voice of America.",
    ],
)
def test_programme_names_openings_and_closings(text: str) -> None:
    assert classify(text) == ("programme", len(text.split()))


def test_an_invitation_to_comment() -> None:
    text = "We want to hear from you. Write to us in the Comments section, or on our Facebook page."
    assert classify(text) == ("call_to_action", len(text.split()))


def test_a_speaker_label_is_boilerplate_but_what_the_speaker_says_is_not() -> None:
    quote = 'MIKE LIZOTTE: "If you want that bulb to survive, you would need to dig it out."'
    assert classify(quote) == ("script", 2)
    assert classify(
        "Steve Ember: In nineteen fifty-eight Burl Ives appeared in a western movie."
    ) == (
        "script",
        2,
    )


def test_a_stage_direction_before_a_label_is_dropped_first() -> None:
    assert classify("(MUSIC) DOUG JOHNSON: Our show is about the weather this week.") == (
        "script",
        2,
    )


@pytest.mark.parametrize(
    "text",
    [
        "The mayor said the new park will open next spring.",
        "I'm sorry, I can't come to the party tonight.",
        "I am Vietnamese and I live in Hanoi with my family.",
        "This is a story about a young girl and her dog.",
        "Note: this recipe needs two eggs.",
        "Closing Thoughts",
        "She explained that the voice of America is a news service.",
        "Doug Johnson wrote a letter to his mother every week.",
    ],
)
def test_ordinary_text_is_not_boilerplate(text: str) -> None:
    assert classify(text) is None
