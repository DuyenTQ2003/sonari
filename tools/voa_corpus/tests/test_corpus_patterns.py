"""Structural rules (frames/patterns.tsv): closed grammars only (ADR-0008 5.3 and its Notes).

Open slots were tried and rejected: a rule whose variable part is any text can remove a sentence
somebody wrote. What stays is a rule whose variable part is a fixed alternation, a date, or a cue
between parentheses, where the text itself marks the boundary. A line is removed when `classify`
says every word of it is boilerplate.
"""

import re

import pytest
from voa_corpus.boilerplate import HERE, classify
from voa_corpus.trim import trim


def removed(line: str) -> bool:
    hit = classify(line)
    return bool(hit) and hit[1] >= len(line.split())


METADATA = ["Broadcast: December 21, 2004", "[Broadcast May 6, 2004]", "Broadcast: April 22, 2003"]
CUES = [
    '(MUSIC: "Let\'s Go Get Stoned")',
    "((MUSIC: FIFE AND DRUMS))",
    '((TAPE: "I have a dream"))',
    "((CUT 3: WHEN THE SUN GOES DOWN; CDP-28627))",
    "(SOUND: Barking dog)",
]
CLOSED = [
    "On this program we talk about common expressions and phrases in American English.",
    "On this show, we explore words and expressions in the English language.",
    "VITA is on the Internet at v-i-t-a dot o-r-g. (vita.org.)",
    "You can contact VITA through the Internet at its World Wide Web address, "
    "w-w-w dot v-i-t-a dot o-r-g.",
    "Dorothy Gundy produced the video.",
    "Gary Garriott was the editor.",
]


@pytest.mark.parametrize("line", METADATA + CUES + CLOSED)
def test_frame_the_closed_rules_must_remove(line: str) -> None:
    assert removed(line)


# Frame that only an open slot could catch. It is left in: a line that stays costs one passage a
# cut that it still needs, a sentence that goes by mistake costs a lesson nobody notices.
LEFT_IN = [
    "tradition \u2013 n. a way of thinking, behaving, or doing something that has been used by the "
    "people in a particular group, family, society, etc., for a long time",
    "bold \u2013adj. strong, clear and without fear",
    "In the comments section, share a story of salt from your culture.",
    "Post your thoughts in the comment section.",
    "Give us your reaction on our Facebook page!",
    "Are you planning to see the movie? Let us know in the comments section.",
    "Now, a special Words and their Stories for New Years.",
    "You can get more information about solar food dryers from the group Volunteers in "
    "Technical Assistance.",
    "Christopher Jones Cruise read the passage from Jack London\u2019s \u201cThe Sea Wolf.\u201d",
    "Yaroslav Khrokalo wrote this lesson with Gena Bennett for VOA Learning English.",
]


@pytest.mark.parametrize("line", LEFT_IN)
def test_a_frame_line_that_needs_an_open_slot_is_left_in(line: str) -> None:
    assert not removed(line)


KEPT = [
    # a definition-shaped sentence that is not a glossary entry
    "The tradition \u2013 n. a way of life \u2013 is old.",
    "tradition - it is important to keep it.",
    # a date that is not a broadcast line
    "The broadcast was on May 6, 2004.",
    "Broadcast news is changing.",
    # a parenthesis that is the text
    "(Music is his passion.)",
    "(Sound familiar?)",
    "(The security guard takes Pete out. Anna watches the movie and eats quietly.)",
    "(At the mailbox)",
    # a sentence about a channel or a site that is not an invitation
    "Facebook users can share photos in the comments section.",
    "Share the video with your friends.",
    "Tell the story on Twitter.",
    "He wrote to us at the newspaper.",
    "Write your name on the paper.",
    "The comments section of the site was full of angry posts.",
    "Share your location with friends on Facebook.",
    "If you want to share photos, tap the Share button on the screen.",
    "Together, they formed a team that won the cup.",
    "My deadline for Words and Their Stories is every Thursday.",
    "Now, Words and Their Stories is a program that I like because it teaches me many things "
    "about the way people speak.",
    "I read about Words and Their Stories in the newspaper.",
    "On today's program, we talk about expressions related to books.",
    "On this program we talk about the history of Texas.",
    # questions that are the text
    "Do you like pizza? I do.",
    "Do you remember where you were? No, I do not.",
    # a credit-shaped sentence about somebody who is not VOA staff, or about a film
    "Sam Mendes directed the film Skyfall for the studio.",
    "The book was written by a teacher who lived in Texas.",
    "The editor was a teacher who lived in Texas.",
    "The stage direction (MUSIC: loud) is written in the margin of the script.",
]


@pytest.mark.parametrize("line", KEPT)
def test_the_nearest_content_is_kept_whole(line: str) -> None:
    assert not removed(line)


INVITATION = "We want to hear from you. Write to us in the Comments Section."


@pytest.mark.parametrize(
    "question",
    [
        "What can you do?",
        "How might you negotiate a lower price?",
        "Have you updated your phone? Have you tried the new features?",
        "In your country, what jobs do women do that are not traditional?",
    ],
)
def test_a_question_beside_an_invitation_is_left_in(question: str) -> None:
    """The open-slot rule "a question beside an invitation" removed the first two, which are
    exercise questions of the lesson (ADR-0008 Notes). No question is removed by its neighbour."""
    t = trim(["Apple released the update last week.", question, INVITATION])
    assert question in t.kept


# A character class or a wildcard that repeats is an open slot. The one allowed is a cue between
# parentheses: the text marks where it ends, and the keyword and colon alone identify the line.
OPEN_SLOT = re.compile(r"\[[^\]]*\](?:[*+]|\{)|\.(?:[*+]|\{)|\\[wWsS](?:[*+]|\{)")
CUE_BODY = "[^()]{1,100}"


def patterns() -> list[str]:
    lines = (HERE / "frames" / "patterns.tsv").read_text("utf-8").splitlines()
    return [line.split("\t")[3] for line in lines if line and not line.startswith("#")]


def test_no_rule_has_an_open_slot() -> None:
    rules = patterns()
    assert rules
    assert [rx for rx in rules if OPEN_SLOT.search(rx.replace(CUE_BODY, ""))] == []


def test_the_cue_is_the_only_rule_with_a_slot_between_parentheses() -> None:
    assert [rx for rx in patterns() if CUE_BODY in rx and not rx.startswith(r"^\(")] == []
    assert len([rx for rx in patterns() if CUE_BODY in rx]) == 1
