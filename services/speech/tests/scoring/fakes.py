"""A real Pronouncer over a fake dictionary: no NLTK data, no 2 s g2p_en load."""

import numpy as np
from tests.g2p.fakes import FakeBackend

from sonari_speech.g2p import Pronouncer
from sonari_speech.scoring.gop import Vocab

DICTIONARY = {
    "one": "W AH1 N",
    "think": "TH IH1 NG K",
    "tink": "T IH1 NG K",
    "you": "Y UW1",
    "took": "T UH1 K",
}


def fake_pronouncer() -> Pronouncer:
    return Pronouncer(FakeBackend(DICTIONARY), lexicon={})


def posteriors(vocab: Vocab, frames: list[str | None], p: float = 0.9) -> np.ndarray:
    """Log posteriors with probability p on one token per frame (None: the blank)."""
    n = len(vocab.ids)
    probs = np.full((len(frames), n), (1 - p) / (n - 1), dtype=np.float64)
    for t, token in enumerate(frames):
        probs[t, vocab.blank if token is None else vocab.ids[token]] = p
    return np.log(probs).astype(np.float32)
