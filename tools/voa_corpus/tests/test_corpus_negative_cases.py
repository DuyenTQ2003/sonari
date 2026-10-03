"""The standing negative cases of ADR-0008 section 4: lines a trim must never remove.

A line is *removed* when `classify` says every word of it is boilerplate. A speaker label that
keeps its speech is not removed: the label's words are reported and the line stays whole.
Every case runs with a straight (') and a curly (’) apostrophe, because the corpus uses both.
"""

import pytest
from voa_corpus.boilerplate import classify

APOSTROPHES = ("'", "’")


def removed_whole(line: str) -> bool:
    hit = classify(line)
    return bool(hit) and hit[1] >= len(line.split())


KEPT = [
    # Speech behind a speaker label
    'MIKE LIZOTTE: "If you want that bulb to survive, you would need to dig it out."',
    "DOUG JOHNSON: I'm Vietnamese and I think English is hard.",
    'JOHN KERRY: "We want to hear from you, the voters, before we decide."',
    # An ordinary sentence that starts like a sign-off
    "I am Vietnamese and I live in Hanoi with my family.",
    "I'm Vietnamese and I live in Hanoi with my family.",
    "I'm Vietnamese and I want to study in America.",
    "This is Vietnam and the weather is hot all year.",
    "I'm Anna. I'm from Vietnam and I study English.",
    "I'm Zed Quux.",  # a name that is not on the staff list
    # A short sentence that mentions the Voice of America or a programme
    "She explained that the voice of America is a news service.",
    "He has worked on the Voice of America for ten years.",
    "She said the story was first broadcast on the Voice of America in 1962.",
    "He teaches special English classes at a school in Hanoi.",
    # VOA's own sentences that name the programme or the service
    "But, the majority of the VOA Learning English audience lives in places where English is "
    "not the main language.",
    "My deadline for Words and Their Stories is every Thursday. When I meet my deadline, "
    "I can relax and enjoy my Friday.",
    "VOA Learning English recently spoke with Jordan as well as Salih Williams (no relation to "
    "Jordan), the director of the media program.",
    # A sign-off glued to a sentence of content: the line stays whole
    "There are several of those. So, don't forget to listen next week for another Words and "
    "Their Stories to learn more.",
    "I'm Larry West. Today, Maurice Joyce and I continue the story of the American Civil War.",
    "Did you enjoy this story? We want to hear from you. Tell us which animal you like best.",
]


@pytest.mark.parametrize("apostrophe", APOSTROPHES)
@pytest.mark.parametrize("line", KEPT)
def test_a_line_that_carries_content_is_never_removed(line: str, apostrophe: str) -> None:
    assert not removed_whole(line.replace("'", apostrophe))


REMOVED = [
    "I'm Bryan Lynn.",
    "And I'm Caty Weaver.",
    "VOICE ONE: I'm Bryan Lynn.",
    "STEVE EMBER: And I'm Bob Doughty.",
    "I'm Doug Johnson. I hope you enjoyed our program today.",
    "This is Steve Ember with the VOA Special English Education Report.",
    "Join us again next week for AMERICAN MOSAIC, VOA's radio magazine in Special English.",
    "We want to hear from you. Write to us in the Comments Section or on our Facebook page.",
    "Faith Pirlo wrote this lesson for VOA Learning English.",
    "And I'm Dr. Jill Robbins.",
]


@pytest.mark.parametrize("apostrophe", APOSTROPHES)
@pytest.mark.parametrize("line", REMOVED)
def test_a_line_that_is_all_frame_is_still_removed(line: str, apostrophe: str) -> None:
    assert removed_whole(line.replace("'", apostrophe))


def test_a_sign_off_glued_to_content_is_reported_but_not_removable() -> None:
    kind, words = classify("I'm Larry West. Today, Maurice Joyce and I continue the story.") or (
        "",
        0,
    )
    assert kind == "presenter"
    assert words == 3  # "I'm Larry West." stays in the text, so it still blocks "as is"
