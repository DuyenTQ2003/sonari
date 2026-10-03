"""Contractions that CMUdict lacks: pronounce the stem, then attach the clitic.

CMUdict covers the common ones ("don't", "I'm", "could've"), so this is a fallback for
the rest ("mustn't", "Anna's"). Works on ARPAbet phones with stress digits.
"""

import re
from collections.abc import Sequence

from sonari_speech.phoneset.mapping import VOWELS, split_stress

# A stem has two letters or more, except "i" ("I'm", "I'll").
_CLITIC = re.compile(r"(?P<stem>[a-z]{2,}|i)(?P<clitic>n't|'s|'d|'ll|'re|'ve|'m)")
_SIBILANTS = frozenset({"S", "Z", "SH", "ZH", "CH", "JH"})
_VOICELESS = frozenset({"P", "T", "K", "F", "TH"})


def split_clitic(word: str) -> tuple[str, str] | None:
    """("couldn't") -> ("could", "n't"); None when the word is not stem plus clitic."""
    m = _CLITIC.fullmatch(word)
    return None if m is None else (m["stem"], m["clitic"])


def attach_clitic(stem_phones: Sequence[str], clitic: str) -> list[str]:
    """ARPAbet of stem plus clitic, e.g. K AE1 T + 's -> K AE1 T S."""
    base, _ = split_stress(stem_phones[-1])
    vowel_final = base in VOWELS
    schwa = [] if vowel_final else ["AH0"]
    if clitic == "n't":
        suffix = [*schwa, "N", "T"]
    elif clitic == "'s":
        suffix = ["IH0", "Z"] if base in _SIBILANTS else ["S" if base in _VOICELESS else "Z"]
    elif clitic == "'ll":
        suffix = [*schwa, "L"]
    elif clitic == "'ve":
        suffix = [*schwa, "V"]
    elif clitic == "'d":
        suffix = [*schwa, "D"]
    elif clitic == "'m":
        suffix = ["M"]
    elif clitic == "'re":
        suffix = ["ER0"]
    else:
        raise ValueError(f"unknown clitic: {clitic!r}")
    return [*stem_phones, *suffix]
