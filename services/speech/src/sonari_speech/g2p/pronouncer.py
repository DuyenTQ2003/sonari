"""Reference text -> expected espeak tokens, per word.

Order of lookup for a word: lexicon override, CMUdict, stem plus clitic (contractions
CMUdict lacks), g2p_en's neural guess. No generated English is involved: the text is the
reference sentence, only its pronunciation is derived.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from sonari_speech.g2p.contractions import attach_clitic, split_clitic
from sonari_speech.g2p.lexicon import load_lexicon
from sonari_speech.g2p.text import normalize_word, number_to_words, tokenize
from sonari_speech.phoneset.mapping import load_table, split_stress, to_espeak

Source = Literal["lexicon", "dictionary", "contraction", "predicted", "number"]


class PronunciationBackend(Protocol):
    """What the pronouncer needs from g2p_en; tests substitute a fake."""

    def lookup(self, word: str) -> Sequence[str] | None:
        """ARPAbet of a dictionary word (first variant), None when the word is unknown."""

    def predict(self, word: str) -> Sequence[str]:
        """The neural model's ARPAbet guess for an unknown word."""


@dataclass(frozen=True, slots=True)
class WordPron:
    """Expected pronunciation of one word of the reference text."""

    text: str  # as written in the reference, for the UI
    start: int  # character span of `text` in the reference
    end: int
    arpabet: tuple[str, ...]
    tokens: tuple[str, ...]  # espeak tokens the model should emit for this word
    source: Source


class Pronouncer:
    """Turns reference text into one `WordPron` per word, with the UI spans kept."""

    def __init__(
        self, backend: PronunciationBackend, lexicon: Mapping[str, Sequence[str]] | None = None
    ) -> None:
        self._backend = backend
        self._lexicon = load_lexicon() if lexicon is None else lexicon
        self._phones = frozenset(load_table()["phones"])

    def pronounce(self, text: str) -> list[WordPron]:
        words = []
        for token in tokenize(text):
            if token.kind == "number":
                # Each spoken word is mapped on its own: IY0 ends "twenty" even when "one" follows.
                parts = [self._word(w)[0] for w in number_to_words(token.text)]
                source: Source = "number"
            else:
                phones, source = self._word(normalize_word(token.text))
                parts = [phones]
            words.append(
                WordPron(
                    token.text,
                    token.start,
                    token.end,
                    tuple(p for part in parts for p in part),
                    tuple(t for part in parts if part for t in to_espeak(part)),
                    source,
                )
            )
        return words

    def _word(self, word: str) -> tuple[list[str], Source]:
        if (phones := self._lexicon.get(word)) is not None:
            return list(phones), "lexicon"
        if (found := self._backend.lookup(word)) is not None:
            return self._valid(found), "dictionary"
        if (parts := split_clitic(word)) is not None and (stem := self._stem(parts[0])):
            return attach_clitic(stem, parts[1]), "contraction"
        return self._valid(self._backend.predict(word.replace("'", ""))), "predicted"

    def _stem(self, stem: str) -> list[str]:
        if (phones := self._lexicon.get(stem)) is not None:
            return list(phones)
        found = self._backend.lookup(stem)
        return self._valid(found if found is not None else self._backend.predict(stem))

    def _valid(self, phones: Sequence[str]) -> list[str]:
        """Keep the ARPAbet phones the table knows; the neural model can emit "<unk>"."""
        kept = []
        for phone in phones:
            try:
                base, _ = split_stress(phone)
            except ValueError:
                continue
            if base in self._phones:
                kept.append(phone)
        return kept
