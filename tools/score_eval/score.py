"""Raw GOP per phoneme for a clip, per reference, exactly as /v1/score computes it.

Needs the speech service's environment (`PYTHONPATH=tools uv run --directory services/speech`).
No verdict is taken here: the thresholds are applied later (analyse.py), so one run serves
v1 and any candidate v2. Each word keeps its en-us phonemes and, where a further reference
gives it a different form, the phonemes of that alignment as scoring/accents.py makes it:
"gb" (espeak-ng en-gb) and "weak" (one entry per rank of g2p/weak_forms.yaml).
"""

import subprocess
from typing import Any

from sonari_speech.g2p import G2pEnBackend, Pronouncer, WordPron
from sonari_speech.g2p.espeak import EspeakReference
from sonari_speech.g2p.weak_forms import load_weak_forms, weak_references
from sonari_speech.runtime.model import FRAME_S
from sonari_speech.runtime.service import Analysis, SpeechRuntime
from sonari_speech.scoring.accents import substitute
from sonari_speech.scoring.align import TooFewFrames
from sonari_speech.scoring.gop import PhonemeGop, Vocab, load_vocab, phoneme_gops
from sonari_speech.settings import Settings


def to_wav(path: str) -> bytes:
    """Any file ffmpeg reads (LibriSpeech is FLAC, which the service refuses) -> 16 kHz WAV."""
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "wav", "-"]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


class ClipScorer:
    def __init__(self) -> None:
        self.runtime = SpeechRuntime(Settings(cores=1))
        self.vocab: Vocab = load_vocab()
        self.pronouncer = Pronouncer(G2pEnBackend())
        self.british = EspeakReference(self.vocab.ids)
        self.weak = load_weak_forms(self.vocab.ids)

    async def start(self) -> None:
        await self.runtime.start()
        if not self.runtime.ready:
            raise RuntimeError("the model did not load")

    async def score(self, data: bytes, text: str) -> dict[str, Any]:
        words = self.pronouncer.pronounce(text)
        analysis = await self.runtime.analyse(data)
        references = [self.british.tokens(words), *weak_references(words, self.weak)]
        us = self._split(words, analysis)
        gb, *weak = (self._alternative(words, r, analysis) for r in references)
        scored = [
            {"text": w.text, "us": us[i], "gb": gb[i], "weak": [a[i] for a in weak]}
            for i, w in enumerate(words)
        ]
        return {"speech_s": analysis.speech_s, "words": scored}

    def _alternative(
        self, words: list[WordPron], reference: list[tuple[str, ...] | None], analysis: Analysis
    ) -> list[list[dict[str, Any]] | None]:
        """Per word: its phonemes under `reference`, None where it adds no different form."""
        swapped, differs = substitute(words, reference)
        try:
            scored = self._split(swapped, analysis) if any(differs) else None
        except TooFewFrames:
            scored = None
        return [scored[i] if scored is not None and d else None for i, d in enumerate(differs)]

    def _split(self, words: list[WordPron], analysis: Analysis) -> list[list[dict[str, Any]]]:
        """Raises TooFewFrames when the sentence does not fit the frames."""
        tokens = [t for w in words for t in w.tokens]
        gops = iter(phoneme_gops(analysis.log_probs, tokens, self.vocab))
        return [[_row(next(gops)) for _ in w.tokens] for w in words]


def _row(g: PhonemeGop) -> dict[str, Any]:
    at = round(g.start * FRAME_S, 2)  # in the trimmed audio
    return {"expected": g.expected, "gop": round(g.gop, 3), "heard": g.heard, "start_s": at}
