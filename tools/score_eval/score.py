"""Raw GOP per phoneme for a clip, per accent, exactly as /v1/score computes it.

Needs the speech service's environment (`PYTHONPATH=tools uv run --directory services/speech`).
No verdict is taken here: the thresholds are applied later (analyse.py), so one run serves
v1 and any candidate v2. Each word keeps its en-us phonemes and, when espeak-ng gives a
different British form, its en-gb phonemes from the second alignment, as scoring/accents.py.
"""

import subprocess
from dataclasses import replace
from typing import Any

from sonari_speech.g2p import G2pEnBackend, Pronouncer, WordPron
from sonari_speech.g2p.espeak import EspeakReference
from sonari_speech.runtime.model import FRAME_S
from sonari_speech.runtime.service import Analysis, SpeechRuntime
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

    async def start(self) -> None:
        await self.runtime.start()
        if not self.runtime.ready:
            raise RuntimeError("the model did not load")

    async def score(self, data: bytes, text: str) -> dict[str, Any]:
        words = self.pronouncer.pronounce(text)
        analysis = await self.runtime.analyse(data)
        british = self.british.tokens(words)
        return {"speech_s": analysis.speech_s, "words": self._words(words, british, analysis)}

    def _words(
        self, words: list[WordPron], british: list[tuple[str, ...] | None], analysis: Analysis
    ) -> list[dict[str, Any]]:
        us = self._split(words, analysis)
        differs = [gb is not None and gb != w.tokens for w, gb in zip(words, british, strict=True)]
        gb_words = [
            replace(w, tokens=gb) if d and gb else w
            for w, gb, d in zip(words, british, differs, strict=True)
        ]
        try:
            gb = self._split(gb_words, analysis) if any(differs) else None
        except TooFewFrames:
            gb = None
        return [
            {"text": w.text, "us": us[i], "gb": gb[i] if gb is not None and differs[i] else None}
            for i, w in enumerate(words)
        ]

    def _split(self, words: list[WordPron], analysis: Analysis) -> list[list[dict[str, Any]]]:
        """Raises TooFewFrames when the sentence does not fit the frames."""
        tokens = [t for w in words for t in w.tokens]
        gops = iter(phoneme_gops(analysis.log_probs, tokens, self.vocab))
        return [[_row(next(gops)) for _ in w.tokens] for w in words]


def _row(g: PhonemeGop) -> dict[str, Any]:
    at = round(g.start * FRAME_S, 2)  # in the trimmed audio
    return {"expected": g.expected, "gop": round(g.gop, 3), "heard": g.heard, "start_s": at}
