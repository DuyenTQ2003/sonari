"""Structural rules (frames/patterns.tsv): anchored at both ends, with closed words at the ends.

Each family has the lines it must remove and the nearest lines of content it must keep (ADR-0008
section 5). A line is removed when `classify` says every word of it is boilerplate.
"""

import pytest
from voa_corpus.boilerplate import classify, classify_all


def removed(line: str) -> bool:
    hit = classify(line)
    return bool(hit) and hit[1] >= len(line.split())


GLOSSARY = [
    "tradition \u2013 n. a way of thinking, behaving, or doing something that has been used by the "
    "people in a particular group, family, society, etc., for a long time",
    "bold \u2013adj. strong, clear and without fear",
    "pitch in \u2013v. to contribute to a common task",
    "of course \u2013 used to show that what is being said is very obvious or generally known",
    "a wink and a nod \u2013 exp. A sly, subtle signal used to communicate a piece of information",
]
METADATA = ["Broadcast: December 21, 2004", "[Broadcast May 6, 2004]", "Broadcast: April 22, 2003"]
CUES = [
    '(MUSIC: "Let\'s Go Get Stoned")',
    "((MUSIC: FIFE AND DRUMS))",
    '((TAPE: "I have a dream"))',
    "((CUT 3: WHEN THE SUN GOES DOWN; CDP-28627))",
    "(SOUND: Barking dog)",
]
INVITATIONS = [
    "In the comments section, share a story of salt from your culture.",
    "Let us know in the comments below or write to us at learningenglish@voanews.com.",
    "Post your thoughts in the comment section.",
    "Give us your reaction on our Facebook page!",
    "Write your answers in the comments section.",
    "You can also find us on Facebook, Twitter and YouTube at VOA Learning English.",
    "Our e-mail address is word@voanews.com.",
    "Are you planning to see the movie? Let us know in the comments section.",
    "Do you have rodeos where you live? Let us know. Post your thoughts in the comment section.",
    "If you liked this week's story about fish, let us know in the Comments Section.",
    "And don't forget to tell us your answers in the comments area.",
    "Anna: Until next time!",
    "On this program we talk about common expressions and phrases in American English.",
    "On this show, we explore words and expressions in the English language.",
    "Now, a special Words and their Stories for New Years.",
    "Hello, I'm Anna Matteo with the Learning English program Words and Their Stories.",
    "That's Words and Their Stories for today, with a song.",
    "You can get more information about solar food dryers from the group Volunteers in "
    "Technical Assistance. VITA is on the Internet at v-i-t-a dot o-r-g. (vita.org.)",
    "Together, they form the living speech of the American people.",
]
CREDITS = [
    "Yaroslav Khrokalo wrote this lesson for VOA Learning English.",
    "Dorothy Gundy produced the video.",
    "Christopher Jones Cruise read the passage from Jack London’s “The Sea Wolf.”",
    "Yaroslav Khrokalo wrote this lesson with Gena Bennett for VOA Learning English.",
    "You can get more information about windbreaks from the group Volunteers in Technical "
    "Assistance. You can contact VITA through the Internet at its World Wide Web address, "
    "w-w-w dot v-i-t-a dot o-r-g.",
]


@pytest.mark.parametrize("line", GLOSSARY + METADATA + CUES + INVITATIONS + CREDITS)
def test_frame_the_rules_must_remove(line: str) -> None:
    assert removed(line)


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
]


@pytest.mark.parametrize("line", KEPT)
def test_the_nearest_content_is_kept_whole(line: str) -> None:
    assert not removed(line)


def test_a_line_of_reader_questions_goes_when_it_stands_next_to_an_invitation() -> None:
    questions = "Have you updated your phone? Have you tried the new features?"
    invitation = "We want to hear from you. Write to us in the Comments Section."
    text = "Apple released the update last week."
    before = classify_all([text, questions, invitation])
    assert before[1] == ("call_to_action", len(questions.split()))
    after = classify_all([invitation, questions, text])
    assert after[1] == ("call_to_action", len(questions.split()))


def test_reader_questions_alone_stay() -> None:
    questions = "Have you updated your phone? Have you tried the new features?"
    text = "Apple released the update last week."
    assert classify_all([text, questions, text])[1] is None


def test_a_question_that_is_not_addressed_to_the_reader_stays_beside_an_invitation() -> None:
    question = "What did the minister say?"
    invitation = "We want to hear from you. Write to us in the Comments Section."
    assert classify_all([question, invitation])[0] is None


def test_a_short_heading_question_stays_beside_an_invitation() -> None:
    heading = "What can you do?"
    invitation = "Write us in the Comments Section of our website."
    text = "The word would has many other meanings."
    assert classify_all([invitation, heading, text])[1] is None


def test_an_exercise_question_stays_beside_an_instruction_that_is_not_an_invitation() -> None:
    question = "How might you negotiate a lower price?"
    instruction = "Pause the audio to consider your answer."
    assert classify_all(["Ten dollars.", question, instruction])[1] is None


def test_a_single_long_question_beside_an_invitation_goes() -> None:
    question = "In your country, what jobs do women do that are not traditional?"
    invitation = "We want to hear from you. Write to us in the Comments Section."
    assert classify_all([question, invitation])[0] == ("call_to_action", len(question.split()))


def test_two_blocks_of_questions_in_a_row_before_an_invitation_both_go() -> None:
    first = "Have you seen the new button? Would you use it? Do you hope it comes to your phone?"
    second = "Would you rather rate a show with stars? Do you like the matching feature?"
    invitation = "Share your thoughts in the Comments Section below."
    hits = classify_all(["Netflix added a button.", second, first, invitation])
    assert hits[1] and hits[2] and hits[0] is None


def test_the_chain_stops_after_one_step() -> None:
    q = "Have you seen the new button? Would you use it? Do you hope it comes to your phone?"
    hits = classify_all([q, q, q, "Share your thoughts in the Comments Section below."])
    assert hits[0] is None and hits[1] and hits[2]
