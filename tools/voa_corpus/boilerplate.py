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
EDITORIAL = ("script", "presenter", "programme", "call_to_action")  # not furniture


def fold(text: str) -> str:
    """Lower case, straight quotes, no invisible characters."""
    return INVISIBLE.sub("", text).translate(QUOTES).lower()


def _data_lines(path: Path) -> list[str]:
    lines = path.read_text("utf-8").splitlines()
    return [line for line in lines if line.strip() and not line.startswith("#")]


def _names() -> re.Pattern[str]:
    names = sorted((fold(n) for n in _data_lines(HERE / "frames" / "staff.txt")), key=len)
    return re.compile(rf"(?<![\w'])(?:{'|'.join(re.escape(n) for n in reversed(names))})(?![\w'])")


def _slot(file: str, before: str = "", after: str = "") -> re.Pattern[str]:
    words = sorted((fold(w) for w in _data_lines(HERE / "frames" / file)), key=len, reverse=True)
    return re.compile(
        rf"(?<![\w']){before}(?:{'|'.join(re.escape(w) for w in words)}){after}(?![\w'])"
    )


STAFF = _names()
PROGRAMMES = _slot("programmes.txt")
REPORTS = _slot("report_topics.txt", r"(?:voa )?(?:(?:special|learning) english )?", " report")
NAMES_IN_A_ROW = re.compile(r"<p>(?:(?:,| and|, and) ?<p>)+")


def normalise(sentence: str) -> str:
    """The form a sentence is listed in. Closed lists become slots: staff names `<p>` (a run of
    names is one slot), programme titles `<prog>`, report topics `<rep>`. No commas, no double
    quotes (a title in curly quotes is the same slot), one dash form, no ellipsis and no closing
    punctuation."""
    s = NAMES_IN_A_ROW.sub("<p>", STAFF.sub("<p>", fold(sentence)))
    s = REPORTS.sub("<rep>", PROGRAMMES.sub("<prog>", s))
    s = re.sub(r"\.{2,}|…", " ", s)
    s = re.sub(r"\s*(?:--+|\u2013|\u2014)\s*|\s-\s", " - ", s)  # one dash form
    s = re.sub(r"\s+", " ", s.replace(",", "").replace('"', "")).strip()
    return re.sub(r"[\s.!:;_]+$", "", s)


def sentences(text: str) -> list[str]:
    """Split a line into sentences. A trailing run of underscores (a fused separator) is dropped."""
    text = re.sub(r"[_\s]+$", "", INVISIBLE.sub("", text).strip())
    return [s for s in SENTENCE.split(text) if s]


def _frames() -> dict[str, tuple[str, str]]:
    """Listed sentence -> (kind, file it is listed in)."""
    frames: dict[str, tuple[str, str]] = {}
    for name, kind in FRAME_FILES:
        for line in _data_lines(HERE / "frames" / name):
            frames.setdefault(line, (kind, name))
    return frames


def _furniture() -> re.Pattern[str]:
    for line in (HERE / "boilerplate.tsv").read_text("utf-8").splitlines():
        if line and not line.startswith("#"):
            _, flags, rx = line.split("\t")
            return re.compile(rx, re.I if "i" in flags else 0)
    raise ValueError("boilerplate.tsv has no furniture rule")


def _patterns() -> tuple[list[tuple[str, re.Pattern[str]]], list[tuple[str, re.Pattern[str]]]]:
    """(sentence rules, line rules) from patterns.tsv, each (kind, regex)."""
    rules: dict[str, list[tuple[str, re.Pattern[str]]]] = {"sentence": [], "line": []}
    for line in (HERE / "frames" / "patterns.tsv").read_text("utf-8").splitlines():
        if line and not line.startswith("#"):
            scope, kind, flags, rx = line.split("\t")
            rules[scope].append((kind, re.compile(rx, re.I if "i" in flags else 0)))
    return rules["sentence"], rules["line"]


FRAMES = _frames()
FURNITURE = _furniture()
SENTENCE_RULES, LINE_RULES = _patterns()


def sentence_rule(sentence: str) -> tuple[str, str] | None:
    """(kind, rule) of a sentence that is frame, listed or built by a rule, or None. The rule is
    `list:<file>` or `patterns.tsv:sentence:<n>` (n counts the rules of that scope from 1)."""
    form = normalise(sentence)
    if form in FRAMES:
        kind, name = FRAMES[form]
        return kind, f"list:{name}"
    for n, (kind, rx) in enumerate(SENTENCE_RULES, 1):
        if rx.match(form):
            return kind, f"patterns.tsv:sentence:{n}"
    return None


def sentence_kind(sentence: str) -> str | None:
    hit = sentence_rule(sentence)
    return hit[0] if hit else None


Hit = tuple[str, int, str]  # kind, words that are boilerplate, the rule that decided


def _rules(rules: list[str]) -> str:
    return "+".join(dict.fromkeys(rules))


def explain(paragraph: str) -> Hit | None:
    """`classify` with the rule that decided: (kind, words that are boilerplate, rule)."""
    text = INVISIBLE.sub("", paragraph).strip()
    words = len(text.split())
    if not text or FURNITURE.search(text):
        return "furniture", words, "furniture"
    body = DIRECTIONS.sub("", text).strip()
    if not body:
        return "script", words, "direction"  # a stage direction alone
    flat = re.sub(r"\s+", " ", body)
    for n, (kind, rx) in enumerate(LINE_RULES, 1):
        if rx.match(flat):
            return kind, words, f"patterns.tsv:line:{n}"  # a broadcast date, a cue
    label = LABEL.match(body)
    rest = body[label.end() :] if label else body
    lead = ["label"] if label else []
    parts = sentences(rest)
    found = [sentence_rule(s) for s in parts]
    kinds = [f[0] if f else None for f in found]
    rules = [f[1] for f in found if f]
    if parts and all(kinds):
        return kinds[0] or "", words, _rules([*lead, *rules])
    if label:  # the speech stays, and so does its label
        return "script", len(label["who"].split()), "label"
    framed = [(k, s) for k, s in zip(kinds, parts, strict=True) if k]
    if framed:  # a sign-off glued to content: kept whole, the frame words still block
        return framed[0][0], sum(len(s.split()) for _, s in framed), _rules(rules)
    return None


def classify(paragraph: str) -> tuple[str, int] | None:
    """(kind, words that are boilerplate) for a paragraph, or None when it is passage text."""
    hit = explain(paragraph)
    return hit[:2] if hit else None
