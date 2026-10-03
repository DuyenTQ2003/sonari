"""Pronunciation overrides for words g2p_en gets wrong (`lexicon.yaml`)."""

from pathlib import Path

import yaml

from sonari_speech.g2p.text import normalize_word
from sonari_speech.phoneset.mapping import to_espeak

LEXICON_PATH = Path(__file__).with_name("lexicon.yaml")


def load_lexicon(path: Path = LEXICON_PATH) -> dict[str, list[str]]:
    """Word -> ARPAbet phones. Raises ValueError on an entry the pipeline could not use."""
    raw = yaml.safe_load(path.read_text("utf-8")) or {}
    lexicon: dict[str, list[str]] = {}
    for word, entry in raw.items():
        if word == "version":
            continue
        if word != normalize_word(word):
            raise ValueError(f"lexicon key must be lower case with straight apostrophes: {word!r}")
        phones = str((entry or {}).get("arpabet", "")).split()
        if not phones:
            raise ValueError(f"lexicon entry {word!r} has no arpabet")
        to_espeak(phones)  # raises ValueError on an unknown phone
        lexicon[word] = phones
    return lexicon
