"""Log-posteriors + expected words -> one verdict per phoneme, grouped by word.

The GOP formula and the rival are P02's (spikes/gop/run_gop.py), kept as they were:

    gop   = mean over the phoneme's frames of (log p(expected) - max_{q != expected} log p(q))
    heard = the phoneme q with the highest mean log p over those frames

q ranges over phoneme tokens only; blank and `<s> <pad> </s> <unk>` never compete. What
changed from the spike: the whole sentence is aligned, not one word, and the verdict comes
from a versioned thresholds file (thresholds/v1.yaml): correct above `correct_above`, wrong
below `wrong_below`, unclear between.
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
from sonari_speech.scoring.contract import Accent, PhonemeVerdict, Verdict, WordScore

VOCAB_PATH = Path(__file__).with_name("vocab.json")  # facebook/wav2vec2-lv-60-espeak-cv-ft
THRESHOLDS_PATH = Path(__file__).parent / "thresholds" / "v1.yaml"
BLANK = "<pad>"
SPECIAL = frozenset({"<s>", "<pad>", "</s>", "<unk>"})
WORST_FIRST: tuple[Verdict, ...] = ("wrong", "unclear", "correct")


@dataclass(frozen=True, slots=True)
class Thresholds:
    version: str
    correct_above: float
    wrong_below: float

    def verdict(self, gop: float) -> Verdict:
        if gop > self.correct_above:
            return "correct"
        return "wrong" if gop < self.wrong_below else "unclear"


@cache
def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    raw = yaml.safe_load(path.read_text("utf-8"))
    found = Thresholds(str(raw["version"]), float(raw["correct_above"]), float(raw["wrong_below"]))
    if found.wrong_below > found.correct_above:
        raise ValueError(f"{path}: wrong_below is above correct_above")
    return found


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
    reference: Accent = "en-us",
) -> list[WordScore]:
    """Verdicts for every word; `offset_s` maps frame 0 back onto the original recording."""
    gops = iter(phoneme_gops(log_probs, [t for w in words for t in w.tokens], vocab))

    def ms(frame: int) -> int:
        return round((offset_s + frame * FRAME_S) * 1000)

    scored = []
    for word in words:
        verdicts = []
        for g in (next(gops) for _ in word.tokens):
            verdict = thresholds.verdict(g.gop)
            verdicts.append(
                PhonemeVerdict(
                    expected=g.expected,
                    verdict=verdict,
                    heard=None if verdict == "correct" else g.heard,
                    gop=round(g.gop, 3),
                    start_ms=ms(g.start),
                    end_ms=ms(g.end),
                )
            )
        found = {v.verdict for v in verdicts}
        scored.append(
            WordScore(
                text=word.text,
                start=word.start,
                end=word.end,
                verdict=next((v for v in WORST_FIRST if v in found), "unclear"),
                reference=reference,
                correct_phonemes=sum(v.verdict == "correct" for v in verdicts),
                phonemes=verdicts,
            )
        )
    return scored
