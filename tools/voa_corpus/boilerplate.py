"""Which parts of a VOA page are not the passage: page furniture, scripts, hosts, programme names.

The rules are data (`boilerplate.tsv`), taken from the paragraphs that repeat across thousands of
pages; `analyze.py` prints the short repeated paragraphs that no rule catches, so the recall is
visible. A speaker label ("MIKE LIZOTTE:") is boilerplate and the quotation after it is not, so
only the label's words count for such a line.
"""

import re
from pathlib import Path

NAME = r"[A-Z][\w.'’\-]*(?:,? [A-Z][\w.'’\-]*){0,3}"
SPEAKERS = r"voice (?:one|two|three|[123])|host|anncr|announcer|question|answer|reader|narrator"
INVISIBLE = re.compile("[­​﻿]")
DIRECTIONS = re.compile(r"^(?:\(+[^)]*\)+\s*)+")  # "(Music)", "((theme))", "(Music) VOICE ONE:"
# "MIKE LIZOTTE: ..." or "Steve Ember: ...": a speaker, then what they say. A lone Title Case word
# ("Note:") is not a speaker.
LABEL = re.compile(
    rf"^(?P<who>(?i:{SPEAKERS})|[A-Z][A-Z.'’\-]+(?: [A-Z][A-Z.'’\-]+){{0,2}}"
    r"|[A-Z][a-z.'’\-]+(?: [A-Z][a-z.'’\-]+){1,2}) ?:\s+(?=\S)"
)
EDITORIAL = ("script", "presenter", "programme", "call_to_action")  # furniture is page layout


def _load() -> list[tuple[str, re.Pattern[str], int]]:
    rules = []
    for line in (Path(__file__).with_name("boilerplate.tsv")).read_text("utf-8").splitlines():
        if line and not line.startswith("#"):
            kind, limit, flags, rx = line.split("\t")
            rx = rx.replace("<NAME>", NAME).replace("<SPEAKERS>", SPEAKERS)
            rules.append((kind, re.compile(rx, re.I if "i" in flags else 0), int(limit)))
    return rules


FURNITURE, *RULES = _load()


def classify(paragraph: str) -> tuple[str, int] | None:
    """(kind, words that are boilerplate) for a paragraph, or None when it is passage text."""
    text = INVISIBLE.sub("", paragraph).strip()
    words = len(text.split())
    if not text or FURNITURE[1].search(text):
        return "furniture", words
    body = DIRECTIONS.sub("", text).strip()
    if not body:
        return "script", words  # a stage direction alone
    label = LABEL.match(body)
    rest = body[label.end() :] if label else body
    for kind, rx, limit in RULES:
        if len(rest.split()) <= limit and rx.search(rest):
            return kind, words
    return ("script", len(label["who"].split())) if label else None
