"""A second reference accent from espeak-ng: one token tuple per reference word, or None.

The en-us reference is g2p_en through the ARPAbet table (pronouncer.py). It is rhotic, so a
non-rhotic British reading ("for" as fɔː) fails against ɔːɹ; IELTS accepts both. espeak-ng's
en-gb voice gives the British form. The model was trained on espeak-ng phonemes, so its
tokens are already the vocab's; a token the vocab lacks drops that word's British form.

One espeak-ng process per sentence (about 7 ms), one word per input line: espeak-ng answers
one line per input line, citation forms, `_` between phonemes. No language model is
involved: espeak-ng is a rule and dictionary G2P.
"""

import shutil
import subprocess
from collections.abc import Collection, Sequence

from sonari_speech.g2p.pronouncer import WordPron
from sonari_speech.g2p.text import normalize_word, number_to_words

STRESS = str.maketrans("", "", "ˈˌ")
TIMEOUT_S = 2.0


class EspeakUnavailable(RuntimeError):
    """espeak-ng is not installed, or failed."""


def spoken(word: WordPron) -> str:
    """The words to say for one reference word, as the en-us pronouncer reads it."""
    if word.source == "number":
        return " ".join(number_to_words(word.text))
    return normalize_word(word.text)


def parse_line(line: str, vocab: Collection[str]) -> tuple[str, ...] | None:
    """`f_ˈɔː w_ˈɒ_n` -> ("f", "ɔː", "w", "ɒ", "n"); None if a token is not in the vocab."""
    tokens = tuple(t for t in line.translate(STRESS).replace(" ", "_").split("_") if t)
    return tokens if tokens and all(t in vocab for t in tokens) else None


class EspeakReference:
    """`tokens(words)`: the voice's tokens per word; None where it has none the model knows."""

    def __init__(self, vocab: Collection[str], voice: str = "en-gb", binary: str = "espeak-ng"):
        path = shutil.which(binary)
        if path is None:
            raise EspeakUnavailable(f"{binary} is not installed")
        self.voice = voice
        self._cmd = [path, "-q", "--ipa", "--sep=_", "-v", voice]
        self._vocab = vocab
        self.tokens([])  # fail at load, not on the first request

    def tokens(self, words: Sequence[WordPron]) -> list[tuple[str, ...] | None]:
        lines = [spoken(w) for w in words]
        if not lines:
            lines = ["a"]  # the load check: the voice exists and answers
        try:
            done = subprocess.run(
                self._cmd,
                input="\n".join(f"{line}." for line in lines),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as err:
            raise EspeakUnavailable(f"espeak-ng -v {self.voice} failed: {err}") from err
        out = [line for line in done.stdout.splitlines() if line.strip()]
        if not words:
            return []
        if len(out) != len(words):
            return [None] * len(words)  # cannot pair lines with words: no British form at all
        return [parse_line(line, self._vocab) for line in out]
