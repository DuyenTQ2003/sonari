"""Log-posteriors + expected words -> one verdict per phoneme, grouped by word.

The GOP formula and the rival are P02's (spikes/gop/run_gop.py), kept as they were:

    gop   = mean over the phoneme's frames of (log p(expected) - max_{q != expected} log p(q))
    heard = the phoneme q with the highest mean log p over those frames

q ranges over phoneme tokens only; blank and `<s> <pad> </s> <unk>` never compete. What
changed from the spike: the whole sentence is aligned, not one word, and a phoneme is
correct when `gop > gop_min` from a versioned thresholds file (thresholds/v0.yaml).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import yaml

from sonari_speech.g2p import WordPron
from sonari_speech.runtime.model import FRAME_S
from sonari_speech.scoring.align import token_spans, viterbi_align
from sonari_speech.scoring.contract import PhonemeVerdict, WordScore

VOCAB_PATH = Path(__file__).with_name("vocab.json")  # facebook/wav2vec2-lv-60-espeak-cv-ft
THRESHOLDS_PATH = Path(__file__).parent / "thresholds" / "v0.yaml"
BLANK = "<pad>"
SPECIAL = frozenset({"<s>", "<pad>", "</s>", "<unk>"})


@dataclass(frozen=True, slots=True)
class Thresholds:
    version: str
    gop_min: float


@cache
def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    raw = yaml.safe_load(path.read_text("utf-8"))
    return Thresholds(str(raw["version"]), float(raw["gop_min"]))


class Vocab:
    """The model's 392 output tokens: ids, the blank, and which ids are phonemes."""

    def __init__(self, path: Path = VOCAB_PATH) -> None:
        self.ids: dict[str, int] = json.loads(path.read_text("utf-8"))
        self.tokens = {i: token for token, i in self.ids.items()}
        self.blank = self.ids[BLANK]
        self.phonemes = np.array(sorted(i for t, i in self.ids.items() if t not in SPECIAL))


@cache
def load_vocab() -> Vocab:
    return Vocab()


@dataclass(frozen=True, slots=True)
class PhonemeGop:
    expected: str
    gop: float
    heard: str  # the best rival over the segment, reported only when the phoneme is wrong
    start: int  # frame span [start, end) of the aligned segment
    end: int


def phoneme_gops(log_probs: np.ndarray, tokens: Sequence[str], vocab: Vocab) -> list[PhonemeGop]:
    """Align `tokens` to the frames and score each. Raises TooFewFrames when they do not fit."""
    ids = [vocab.ids[t] for t in tokens]
    spans = token_spans(viterbi_align(log_probs, ids, vocab.blank), len(ids))
    out = []
    for token, tid, (start, end) in zip(tokens, ids, spans, strict=True):
        segment = log_probs[start:end]
        rivals = vocab.phonemes[vocab.phonemes != tid]
        rival_lp = segment[:, rivals]
        gop = float(np.mean(segment[:, tid] - rival_lp.max(axis=1)))
        heard = vocab.tokens[int(rivals[rival_lp.mean(axis=0).argmax()])]
        out.append(PhonemeGop(token, gop, heard, start, end))
    return out


def score_words(
    words: Sequence[WordPron],
    log_probs: np.ndarray,
    offset_s: float,
    thresholds: Thresholds,
    vocab: Vocab,
) -> list[WordScore]:
    """Verdicts for every word; `offset_s` maps frame 0 back onto the original recording."""
    gops = iter(phoneme_gops(log_probs, [t for w in words for t in w.tokens], vocab))

    def ms(frame: int) -> int:
        return round((offset_s + frame * FRAME_S) * 1000)

    scored = []
    for word in words:
        verdicts = []
        for g in (next(gops) for _ in word.tokens):
            correct = g.gop > thresholds.gop_min
            verdicts.append(
                PhonemeVerdict(
                    expected=g.expected,
                    correct=correct,
                    heard=None if correct else g.heard,
                    gop=round(g.gop, 3),
                    start_ms=ms(g.start),
                    end_ms=ms(g.end),
                )
            )
        n_correct = sum(v.correct for v in verdicts)
        scored.append(
            WordScore(
                text=word.text,
                start=word.start,
                end=word.end,
                correct=bool(verdicts) and n_correct == len(verdicts),
                correct_phonemes=n_correct,
                phonemes=verdicts,
            )
        )
    return scored
