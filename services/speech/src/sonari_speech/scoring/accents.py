"""Score a sentence against its alternative references; keep the best one per word.

The en-us sentence is aligned first. Then each alternative (the en-gb form, and each rank of
the weak forms of g2p/weak_forms.yaml) is the same sentence with that reference's tokens for
every word that has one that differs, aligned over the same posteriors (one model pass).
Each word takes its verdicts from the alignment that judged it best: fewer "wrong", then
fewer "unclear", then the higher mean GOP; a tie keeps the earlier reference (en-us first).
Neighbouring words may so come from different alignments, and their spans may touch or
overlap by a frame or two.
"""

from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from sonari_speech.g2p import WordPron
from sonari_speech.scoring.align import TooFewFrames
from sonari_speech.scoring.contract import Accent, WordScore
from sonari_speech.scoring.gop import Thresholds, Vocab, score_words

Reference = Sequence[tuple[str, ...] | None]  # tokens per word; None where the word has none
Alternative = tuple[Accent, Reference]  # a weak form of the en-us reading stays "en-us"


def _rank(word: WordScore) -> tuple[int, int, float]:
    verdicts = [p.verdict for p in word.phonemes]
    mean_gop = float(np.mean([p.gop for p in word.phonemes])) if word.phonemes else 0.0
    return verdicts.count("wrong"), verdicts.count("unclear"), -mean_gop


def substitute(
    words: Sequence[WordPron], reference: Reference
) -> tuple[list[WordPron], list[bool]]:
    """`words` with the reference's tokens where they differ from en-us, and where that was."""
    differs = [r is not None and r != w.tokens for w, r in zip(words, reference, strict=True)]
    swapped = [
        replace(w, tokens=r) if d and r is not None else w
        for w, r, d in zip(words, reference, differs, strict=True)
    ]
    return swapped, differs


def score_accents(
    words: Sequence[WordPron],
    alternatives: Sequence[Alternative],
    log_probs: np.ndarray,
    offset_s: float,
    thresholds: Thresholds,
    vocab: Vocab,
) -> list[WordScore]:
    """Raises TooFewFrames only when the en-us sentence does not fit the frames."""
    best = score_words(words, log_probs, offset_s, thresholds, vocab, "en-us")
    for label, reference in alternatives:
        swapped, differs = substitute(words, reference)
        if not any(differs):
            continue
        try:
            scored = score_words(swapped, log_probs, offset_s, thresholds, vocab, label)
        except TooFewFrames:
            continue
        best = [
            min(b, s, key=_rank) if d else b for b, s, d in zip(best, scored, differs, strict=True)
        ]
    return best
