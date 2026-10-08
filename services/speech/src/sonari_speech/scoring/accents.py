"""Score a sentence against the en-us and the en-gb reference; keep the better one per word.

Both references are aligned over the same posteriors (one model pass): the en-us sentence,
then the same sentence with each word's British form where espeak-ng gave one that differs.
Each word then takes its verdicts from the alignment that judged it better: fewer "wrong",
then fewer "unclear", then the higher mean GOP; a tie keeps en-us. Neighbouring words may
so come from different alignments, and their spans may touch or overlap by a frame or two.
"""

from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from sonari_speech.g2p import WordPron
from sonari_speech.scoring.align import TooFewFrames
from sonari_speech.scoring.contract import WordScore
from sonari_speech.scoring.gop import Thresholds, Vocab, score_words

British = Sequence[tuple[str, ...] | None]


def _rank(word: WordScore) -> tuple[int, int, float]:
    verdicts = [p.verdict for p in word.phonemes]
    mean_gop = float(np.mean([p.gop for p in word.phonemes])) if word.phonemes else 0.0
    return verdicts.count("wrong"), verdicts.count("unclear"), -mean_gop


def score_accents(
    words: Sequence[WordPron],
    british: British,
    log_probs: np.ndarray,
    offset_s: float,
    thresholds: Thresholds,
    vocab: Vocab,
) -> list[WordScore]:
    """Raises TooFewFrames only when the en-us sentence does not fit the frames."""
    american = score_words(words, log_probs, offset_s, thresholds, vocab, "en-us")
    differs = [gb is not None and gb != w.tokens for w, gb in zip(words, british, strict=True)]
    if not any(differs):
        return american
    gb_words = [
        replace(w, tokens=gb) if d and gb is not None else w
        for w, gb, d in zip(words, british, differs, strict=True)
    ]
    try:
        gb_scored = score_words(gb_words, log_probs, offset_s, thresholds, vocab, "en-gb")
    except TooFewFrames:
        return american
    return [
        min(us, gb, key=_rank) if d else us
        for us, gb, d in zip(american, gb_scored, differs, strict=True)
    ]
