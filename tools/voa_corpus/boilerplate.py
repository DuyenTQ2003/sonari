"""Which parts of a VOA page are not the passage: page furniture, scripts, hosts, programme names.

ADR-0008 decides what may be cut from a passage: whole lines, and only lines that are frame. So
a line is boilerplate only when **every sentence in it is on a closed list** (`frames/*.txt`),
with the names of VOA staff taken from a second closed list (`frames/staff.txt`). Nothing is
matched by a pattern that could also match a sentence somebody wrote: "I'm Vietnamese and..."
is not a sign-off because Vietnamese is not a presenter, and "on the Voice of America" inside a
sentence is not a programme line because only whole listed sentences count.

`classify` returns `(kind, words)`. `words` equals the line's word count when the whole line is
frame and can be removed. When it is smaller, the line stays and those words are frame that
cannot be cut out of it: a speaker label in front of speech, or a sign-off glued to a sentence
of content. Both still block "as is" and both are kept whole, as the ADR says. The lists come
from the corpus (every sentence found in at least 3 passages, read by hand); `analyze.py` prints
the short paragraphs that no list covers, so the recall is visible.
"""

import re
from pathlib import Path

HERE = Path(__file__).parent
FRAME_FILES = (  # file -> kind it reports; credits and contact lines are programme lines
    ("script.txt", "script"),
    ("presenter.txt", "presenter"),
    ("programme.txt", "programme"),
    ("credits.txt", "programme"),
    ("call_to_action.txt", "call_to_action"),
)
INVISIBLE = re.compile("[­​﻿]")
QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
# A sentence ends at . ! ? or an ellipsis, but not after "Dr." or "Mr." in a name, and not before
# a lower case word ("Mario Ritter, Jr. was the editor.").
SENTENCE = re.compile(r"(?<=[.!?…])(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bMrs\.)\s+(?![a-z])")
# Stage directions: "(MUSIC)", "((theme))", "(Music Bridge)". A closed set, not any parenthesis.
DIRECTIONS = re.compile(
    r"^(?:\(+\s*(?:music(?: bridge)?|theme|sound(?: and music)?|bridge music)\s*\)+\s*)+", re.I
)
SPEAKERS = r"voice (?:one|two|three|[123])|host|anncr|announcer|question|answer|reader|narrator"
# "MIKE LIZOTTE: ..." or "Steve Ember: ...": a speaker, then what they say. A lone Title Case word
# ("Note:") is not a speaker. Only the label's words count when the speech is not frame.
LABEL = re.compile(
    rf"^(?P<who>(?i:{SPEAKERS})|[A-Z][A-Z.'’\-]+(?: [A-Z][A-Z.'’\-]+){{0,2}}"
    r"|[A-Z][a-z.'’\-]+(?: [A-Z][a-z.'’\-]+){1,2}) ?:\s+(?=\S)"
)
EDITORIAL = ("script", "presenter", "programme", "call_to_action")  # furniture is page layout


def fold(text: str) -> str:
    """Lower case, straight quotes, no invisible characters."""
    return INVISIBLE.sub("", text).translate(QUOTES).lower()


def _data_lines(path: Path) -> list[str]:
    lines = path.read_text("utf-8").splitlines()
    return [line for line in lines if line.strip() and not line.startswith("#")]


def _names() -> re.Pattern[str]:
    names = sorted((fold(n) for n in _data_lines(HERE / "frames" / "staff.txt")), key=len)
    return re.compile(rf"(?<![\w'])(?:{'|'.join(re.escape(n) for n in reversed(names))})(?![\w'])")


STAFF = _names()


def normalise(sentence: str) -> str:
    """The form a sentence is listed in: a staff name becomes `<p>`; no commas, no dashes
    variants, no ellipsis and no closing punctuation."""
    s = STAFF.sub("<p>", fold(sentence))
    s = re.sub(r"\.{2,}|…", " ", s)
    s = re.sub(r"\s*(?:--+|\u2013|\u2014)\s*|\s-\s", " - ", s)  # one dash form
    s = re.sub(r"\s+", " ", s.replace(",", "")).strip()
    return re.sub(r"[\s.!:;_]+$", "", s)


def sentences(text: str) -> list[str]:
    """Split a line into sentences. A trailing run of underscores (a fused separator) is dropped."""
    text = re.sub(r"[_\s]+$", "", INVISIBLE.sub("", text).strip())
    return [s for s in SENTENCE.split(text) if s]


def _frames() -> dict[str, str]:
    frames: dict[str, str] = {}
    for name, kind in FRAME_FILES:
        for line in _data_lines(HERE / "frames" / name):
            frames.setdefault(line, kind)
    return frames


def _furniture() -> re.Pattern[str]:
    for line in (HERE / "boilerplate.tsv").read_text("utf-8").splitlines():
        if line and not line.startswith("#"):
            _, flags, rx = line.split("\t")
            return re.compile(rx, re.I if "i" in flags else 0)
    raise ValueError("boilerplate.tsv has no furniture rule")


FRAMES = _frames()
FURNITURE = _furniture()


def classify(paragraph: str) -> tuple[str, int] | None:
    """(kind, words that are boilerplate) for a paragraph, or None when it is passage text."""
    text = INVISIBLE.sub("", paragraph).strip()
    words = len(text.split())
    if not text or FURNITURE.search(text):
        return "furniture", words
    body = DIRECTIONS.sub("", text).strip()
    if not body:
        return "script", words  # a stage direction alone
    label = LABEL.match(body)
    rest = body[label.end() :] if label else body
    parts = sentences(rest)
    kinds = [FRAMES.get(normalise(s)) for s in parts]
    if parts and all(kinds):
        return kinds[0] or "", words  # every sentence is frame: the whole line can go
    if label:
        return "script", len(label["who"].split())  # the speech stays, and so does its label
    framed = [(k, s) for k, s in zip(kinds, parts, strict=True) if k]
    if framed:  # a sign-off glued to content: kept whole, the frame words still block
        return framed[0][0], sum(len(s.split()) for _, s in framed)
    return None
