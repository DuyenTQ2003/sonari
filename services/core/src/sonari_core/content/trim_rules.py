"""What ADR-0008 forbids, as the content service enforces it where a file enters (ADR-0010 6).

The tools (`tools/voa_corpus`) apply the same rules when they choose and write the corpus, and
the service cannot import them, so every number and every count exists here as well. Nothing in
the file is trusted: a record does not choose its cap, and the numbers it declares about its own
trim are derived from the lines it lists. `scripts/tests/test_adr_0008_drift.py` and
`test_adr_0008_constraints_drift.py` compare this module with the tools and with the text of the
ADR. Change a number only with a superseding ADR, and in the same commit as the tools and those
tests.
"""

import re
from collections.abc import Iterable

# ADR-0008 decision 2: a trim may cut at most 5% of the passage's words.
TRIM_CAP = 0.05
# ADR-0008 decision 2: the length window, applied to the trimmed text. Both ends are inclusive.
MIN_WORDS, MAX_WORDS = 250, 1200
# ADR-0008 decision 2: the Flesch-Kincaid grade ceiling. The grade must be below it.
MAX_FK = 7.0
# ADR-0008 decision 1: page furniture is removed and recorded, but is layout, not passage, and
# does not count toward the cap.
FURNITURE = "furniture"

# The corpus tokeniser (`voa_inventory.levels.WORD`): a letter, then letters, apostrophes and
# hyphens. Digits and punctuation are not words. It counts the page (`original_words`) and the
# trimmed text (the window).
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def count_words(lines: Iterable[str]) -> int:
    """Words of these lines as the corpus counts a page and a trimmed text."""
    return sum(len(WORD.findall(line)) for line in lines)


def editorial_words(removed: Iterable[tuple[str, str]]) -> int:
    """Words on the removed `(kind, text)` lines that count against the cap, which the trim
    counts by whitespace (`voa_corpus.trim.Trim.removed_words`): everything but furniture."""
    return sum(len(text.split()) for kind, text in removed if kind != FURNITURE)
