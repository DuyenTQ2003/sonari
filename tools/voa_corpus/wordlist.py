"""CEFR vocabulary levels from a published list, and a token -> level lookup.

The list is the CEFR-J Vocabulary Profile 1.5 (A1-B2, 7,799 headwords; Tono Laboratory, TUFS) and
the Octanove C1/C2 profile 1.0 (2,136 headwords; CC BY-SA 4.0), from
github.com/openlanguageprofiles/olp-en-cefrj at a pinned commit. The CEFR-J terms allow use with
a citation but say nothing about redistribution, so it is not copied into this repository:
`make voa-wordlists` downloads it into `~/.cache/sonari/wordlists` and checks it against
`wordlists.sha256`.

Both lists hold lemmas, so an inflected token ("walked", "children") is looked up through a few
regular suffix rules and a table of irregular forms (`irregular.txt`). The match is approximate.
"""

import csv
from pathlib import Path

HERE = Path(__file__).parent
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
FILES = [line.split()[1] for line in (HERE / "wordlists.sha256").read_text().splitlines()]
IRREGULAR = {
    form: base.lower()
    for line in (HERE / "irregular.txt").read_text("utf-8").splitlines()
    if line and not line.startswith("#")
    for base, forms in [line.split(": ")]
    for form in forms.split()
}
SUFFIXES = (
    ("ies", "y"), ("es", ""), ("s", ""), ("ied", "y"), ("ed", ""), ("ed", "e"), ("ing", ""),
    ("ing", "e"), ("ier", "y"), ("er", ""), ("er", "e"), ("iest", "y"), ("est", ""), ("est", "e"),
    ("ily", "y"), ("ly", ""), ("ness", ""), ("ment", ""),
)  # fmt: skip


def load(directory: Path) -> dict[str, int]:
    """Lowercase headword -> index into LEVELS (the easiest level it is listed at)."""
    table: dict[str, int] = {}
    for name in FILES:
        with (directory / name).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                level = LEVELS.index(row["CEFR"])
                for word in (w.strip() for w in row["headword"].lower().split("/")):
                    if word and " " not in word:
                        table[word] = min(level, table.get(word, level))
    return table


def level_of(word: str, table: dict[str, int]) -> int | None:
    """Index into LEVELS for a lowercase word: itself, its irregular base, then suffix rules."""
    if word in table:
        return table[word]
    if IRREGULAR.get(word) in table:
        return table[IRREGULAR[word]]
    for suffix, replacement in SUFFIXES:
        stem = word[: -len(suffix)] if word.endswith(suffix) else ""
        if len(stem) >= 2:
            doubled = stem[:-1] if stem[-1] == stem[-2] else ""  # "stopp" -> "stop"
            for candidate in (stem + replacement, doubled):
                if candidate in table:
                    return table[candidate]
    return None
