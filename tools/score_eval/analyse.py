"""Verdicts from raw GOPs, the native false-alarm rate, a v2 threshold, word collapse.

Pure stdlib, so `make test-tools` runs it. The per-word choice among the references copies
services/speech/src/sonari_speech/scoring/accents.py (`_rank`): fewer wrong, then fewer
unclear, then the higher mean GOP; a tie keeps the earlier of en-us, en-gb, the weak forms.
It depends on the thresholds, so it is redone for each one. tests/test_analyse.py pins the
rule on hand-made words.
"""

import math
import random
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

CORRECT_ABOVE = 0.0
V1_WRONG_BELOW = -3.4
TARGET = 0.01  # native phonemes marked wrong: strictly under 1%
# A word "fails together" when it has at least this many phonemes and most of them are wrong.
COLLAPSE_MIN_PHONEMES = 2


def verdict(gop: float, wrong_below: float) -> str:
    return "correct" if gop > CORRECT_ABOVE else "wrong" if gop < wrong_below else "unclear"


def _rank(phonemes: list[dict[str, Any]], wrong_below: float) -> tuple[int, int, float]:
    verdicts = [verdict(p["gop"], wrong_below) for p in phonemes]
    mean = sum(p["gop"] for p in phonemes) / len(phonemes) if phonemes else 0.0
    return verdicts.count("wrong"), verdicts.count("unclear"), -mean


def choose(word: dict[str, Any], wrong_below: float) -> tuple[str, list[dict[str, Any]]]:
    """(reference, phonemes) the service would report for this word; `min` keeps the earlier."""
    options = [("en-us", word["us"]), ("en-gb", word["gb"])]
    options += [("weak", rows) for rows in word.get("weak", [])]  # an old file has none
    return min(
        ((n, r) for n, r in options if r is not None), key=lambda o: _rank(o[1], wrong_below)
    )


@dataclass(frozen=True, slots=True)
class Phoneme:
    clip: str
    word: str
    word_index: int
    expected: str
    gop: float
    heard: str
    verdict: str


def phonemes(clips: Iterable[dict[str, Any]], wrong_below: float) -> Iterator[Phoneme]:
    for clip in clips:
        for i, word in enumerate(clip.get("words", [])):
            _, chosen = choose(word, wrong_below)
            for p in chosen:
                v = verdict(p["gop"], wrong_below)
                yield Phoneme(clip["id"], word["text"], i, p["expected"], p["gop"], p["heard"], v)


def wrong_share(clips: list[dict[str, Any]], wrong_below: float) -> float:
    found = [p.verdict == "wrong" for p in phonemes(clips, wrong_below)]
    return sum(found) / len(found)


def propose(clips: list[dict[str, Any]], target: float = TARGET, step: float = 0.1) -> float:
    """The highest threshold, on a 0.1 grid from v1 down, that marks under `target` wrong."""
    t = V1_WRONG_BELOW
    while wrong_share(clips, t) >= target:
        t = round(t - step, 1)
    return t


def quantiles(values: list[float], qs: Iterable[float]) -> dict[float, float]:
    ordered = sorted(values)
    return {q: ordered[min(len(ordered) - 1, int(q * len(ordered)))] for q in qs}


def per_clip(clips: list[dict[str, Any]], wrong_below: float) -> Counter[str]:
    """Wrong phonemes per clip (clips with none included, at 0)."""
    counts: Counter[str] = Counter({c["id"]: 0 for c in clips if "words" in c})
    counts.update(p.clip for p in phonemes(clips, wrong_below) if p.verdict == "wrong")
    return counts


@dataclass(frozen=True, slots=True)
class Collapse:
    observed: int  # words with >= 2 phonemes where most are wrong
    expected: float  # the same count if wrong phonemes fell independently at the overall rate
    wrong_in_collapsed: int  # wrong phonemes that sit in such words
    wrong: int


def collapse(clips: list[dict[str, Any]], wrong_below: float) -> Collapse:
    by_word: dict[tuple[str, int], list[Phoneme]] = {}
    for p in phonemes(clips, wrong_below):
        by_word.setdefault((p.clip, p.word_index), []).append(p)
    counts = [(len(ps), sum(p.verdict == "wrong" for p in ps)) for ps in by_word.values()]
    wrong = sum(k for _, k in counts)
    rate = wrong / sum(n for n, _ in counts)
    long = [(n, k, n // 2 + 1) for n, k in counts if n >= COLLAPSE_MIN_PHONEMES]
    expected = sum(
        math.comb(n, j) * rate**j * (1 - rate) ** (n - j)
        for n, _, most in long
        for j in range(most, n + 1)
    )
    failed = [k for _, k, most in long if k >= most]
    return Collapse(len(failed), expected, sum(failed), wrong)


def bootstrap(
    clips: list[dict[str, Any]], wrong_below: float, rounds: int = 1000
) -> tuple[float, float]:
    """95% interval of the wrong share, resampling whole utterances (seeded)."""
    rng = random.Random(0)
    per = []
    for c in clips:
        ps = list(phonemes([c], wrong_below))
        per.append((sum(p.verdict == "wrong" for p in ps), len(ps)))
    shares = []
    for _ in range(rounds):
        draw = [per[rng.randrange(len(per))] for _ in per]
        shares.append(sum(w for w, _ in draw) / sum(n for _, n in draw))
    shares.sort()
    return shares[int(0.025 * rounds)], shares[int(0.975 * rounds) - 1]


def propose_upper(clips: list[dict[str, Any]], target: float = TARGET) -> float:
    """Like `propose`, but the bootstrap's upper 95% bound must be under `target`."""
    t = propose(clips, target)
    while bootstrap(clips, t)[1] >= target:
        t = round(t - 0.1, 1)
    return t


def without_weak(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same clips scored against en-us and en-gb only: what PR #51 measured."""
    return [c | {"words": [w | {"weak": []} for w in c["words"]]} for c in clips if "words" in c]


def without_words(clips: list[dict[str, Any]], drop: frozenset[str]) -> list[dict[str, Any]]:
    """The same clips with some words removed: a what-if, not a scoring change."""
    return [c | {"words": [w for w in c["words"] if w["text"].lower() not in drop]} for c in clips]
