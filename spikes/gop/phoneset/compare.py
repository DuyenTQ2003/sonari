"""Compare mapped g2p_en output with espeak-ng output for the same word.

Both sides are token lists. `strip_stress` is the only step of the strict comparison.
The fold rules then remove differences that are accent or connected-speech variants
rather than errors, so the mismatches that survive are worth reading. Every rule is
applied to BOTH sides and only ever makes two sequences more equal.
"""

import difflib
import re
from collections.abc import Callable, Sequence

STRESS_MARKS = re.compile(r"[ˈˌ]")
# espeak emits these as single tokens; both sides are split into schwa + consonant.
SYLLABIC = {"əl": ["ə", "l"], "n̩": ["ə", "n"]}
# Reduced vowels: the unstressed vowel of "family" is ɪ or ə depending on the speaker,
# and espeak spells its own reductions ɐ and ᵻ.
REDUCED = frozenset({"ə", "ɐ", "ᵻ", "ɪ"})
FLAP = frozenset({"t", "d", "ɾ"})
VOWEL_TOKENS = frozenset(
    {
        *("ɑː", "æ", "ʌ", "ɔː", "ɔ", "aʊ", "aɪ", "ɛ", "ɜː", "ɚ", "eɪ", "ɪ", "i", "iː", "oʊ"),
        *("ɔɪ", "ʊ", "uː", "ə", "ɐ", "ᵻ", "aɪɚ", "aɪə", "iə", "ɑːɹ", "ɔːɹ", "ɛɹ", "ɪɹ", "ʊɹ"),
    }
)


def strip_stress(tokens: Sequence[str]) -> list[str]:
    """Drop espeak stress marks; a mark may be glued to the following token."""
    stripped = (STRESS_MARKS.sub("", tok) for tok in tokens)
    return [tok for tok in stripped if tok]


def fold_syllabic(tokens: Sequence[str]) -> list[str]:
    """Split syllabic l and n, and treat the glottal stop of "button" as t."""
    out: list[str] = []
    for tok in tokens:
        out.extend(SYLLABIC.get(tok, ["t" if tok == "ʔ" else tok]))
    return out


def fold_reduced(tokens: Sequence[str]) -> list[str]:
    return ["ə" if tok in REDUCED else tok for tok in tokens]


def fold_flap(tokens: Sequence[str]) -> list[str]:
    """US flapping: t, d and ɾ are one class between two vowels ("water", "city")."""
    out = list(tokens)
    for i in range(1, len(out) - 1):
        if out[i] in FLAP and out[i - 1] in VOWEL_TOKENS and out[i + 1] in VOWEL_TOKENS:
            out[i] = "ɾ"
    return out


# Order matters: syllabic splitting exposes the vowel context the flap rule needs.
FOLDS: dict[str, Callable[[Sequence[str]], list[str]]] = {
    "syllabic/glottal": fold_syllabic,
    "reduced vowel": fold_reduced,
    "flap": fold_flap,
}


def fold(tokens: Sequence[str]) -> list[str]:
    out = list(tokens)
    for rule in FOLDS.values():
        out = rule(out)
    return out


def diff_ops(a: Sequence[str], b: Sequence[str]) -> list[tuple[str, str]]:
    """Differing spans as (mapped side, espeak side) strings, in order."""
    sm = difflib.SequenceMatcher(a=list(a), b=list(b), autojunk=False)
    return [
        (" ".join(a[i1:i2]), " ".join(b[j1:j2]))
        for op, i1, i2, j1, j2 in sm.get_opcodes()
        if op != "equal"
    ]


def diff_size(a: Sequence[str], b: Sequence[str]) -> int:
    """Number of tokens inside the differing spans (0 means the lists are equal)."""
    return sum(max(len(x.split()), len(y.split())) for x, y in diff_ops(a, b))


def explaining_folds(a: Sequence[str], b: Sequence[str]) -> list[str]:
    """Names of the fold rules that each shrink the difference, in order."""
    names = []
    left, right = list(a), list(b)
    for name, rule in FOLDS.items():
        before = diff_size(left, right)
        left, right = rule(left), rule(right)
        if diff_size(left, right) < before:
            names.append(name)
    return names
