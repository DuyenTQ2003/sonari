"""A real Pronouncer over a fake dictionary: no NLTK data, no 2 s g2p_en load."""

from collections.abc import Mapping, Sequence

import numpy as np
from tests.g2p.fakes import FakeBackend

from sonari_speech.g2p import Pronouncer, WordPron
from sonari_speech.scoring.gop import Vocab

DICTIONARY = {
    "one": "W AH1 N",
    "think": "TH IH1 NG K",
    "tink": "T IH1 NG K",
    "you": "Y UW1",
    "took": "T UH1 K",
}


# British forms that differ from the en-us ones above; any other word has none.
BRITISH = {"one": ("w", "ɒ", "n")}


def fake_pronouncer() -> Pronouncer:
    return Pronouncer(FakeBackend(DICTIONARY), lexicon={})


class FakeBritish:
    """Stands in for EspeakReference: no espeak-ng process."""

    def __init__(self, forms: Mapping[str, tuple[str, ...]] = BRITISH) -> None:
        self.forms = forms

    def tokens(self, words: Sequence[WordPron]) -> list[tuple[str, ...] | None]:
        return [self.forms.get(w.text.lower()) for w in words]


def fake_british() -> FakeBritish:
    return FakeBritish()


def posteriors(vocab: Vocab, frames: list[str | None], p: float = 0.9) -> np.ndarray:
    """Log posteriors with probability p on one token per frame (None: the blank)."""
    n = len(vocab.ids)
    probs = np.full((len(frames), n), (1 - p) / (n - 1), dtype=np.float64)
    for t, token in enumerate(frames):
        probs[t, vocab.blank if token is None else vocab.ids[token]] = p
    return np.log(probs).astype(np.float32)
