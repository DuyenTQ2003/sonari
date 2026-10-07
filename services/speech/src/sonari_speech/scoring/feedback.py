"""A wrong phoneme -> which fixed Vietnamese explanation to show. No LLM, and no prose here.

The service sends a message key and parameters; the client renders `<key>.why` and
`<key>.how` from apps/web/messages/vi.json. The rules and the evidence behind each are in
feedback.yaml. Order of lookup: the (expected, heard) pair, then the word position
(final consonant, consonant cluster), then `generic`, which names the sound and claims no cause.
"""

import unicodedata
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from sonari_speech.phoneset.mapping import vowel_tokens
from sonari_speech.scoring.contract import Feedback, FeedbackParams, PhonemeVerdict, WordScore

TABLE_PATH = Path(__file__).with_name("feedback.yaml")
KEY_PREFIX = "pronunciation.fix."
FALLBACK_KEY = "generic"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(_Strict):
    cite: str
    checked: str


class Rule(_Strict):
    expected: list[str] | None = None
    heard: str | None = None
    position: Literal["final", "cluster"] | None = None
    key: str
    sources: list[str] = []
    unsourced: str | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if (self.heard is None) == (self.position is None):
            raise ValueError(f"{self.key}: name either `heard` or `position`")
        if self.heard is not None and not self.expected:
            raise ValueError(f"{self.key}: a pair rule needs `expected`")
        if bool(self.sources) == (self.unsourced is not None):
            raise ValueError(f"{self.key}: give `sources` or `unsourced`, not both or neither")
        return self


class Table(_Strict):
    sources: dict[str, Source]
    rules: list[Rule]


@cache
def load_table(path: Path = TABLE_PATH) -> Table:
    return Table.model_validate(yaml.safe_load(path.read_text("utf-8")))


def fold(token: str) -> str:
    """Drop modifier letters and combining marks: tʰ, sʲ, t̪, tː -> t, s, t, t."""
    decomposed = unicodedata.normalize("NFD", token)
    return "".join(c for c in decomposed if unicodedata.category(c) not in ("Mn", "Lm"))


def _matches(rule: Rule, verdict: PhonemeVerdict, final: bool, cluster: bool) -> bool:
    if rule.expected and verdict.expected not in rule.expected:
        return False
    if rule.heard is not None:
        return verdict.heard is not None and fold(verdict.heard) == rule.heard
    return final if rule.position == "final" else cluster


def feedback_for(phonemes: Sequence[PhonemeVerdict], index: int, word: str) -> Feedback | None:
    """Feedback for `phonemes[index]` of `word`; None when it was said correctly."""
    verdict = phonemes[index]
    if verdict.correct or verdict.heard is None:
        return None
    vowels = vowel_tokens()
    consonant = verdict.expected not in vowels
    touching = (phonemes[j].expected for j in (index - 1, index + 1) if 0 <= j < len(phonemes))
    final = consonant and index == len(phonemes) - 1
    cluster = consonant and any(token not in vowels for token in touching)
    key = next(
        (r.key for r in load_table().rules if _matches(r, verdict, final, cluster)), FALLBACK_KEY
    )
    params = FeedbackParams(expected=verdict.expected, heard=verdict.heard, word=word)
    return Feedback(message_key=KEY_PREFIX + key, params=params)


def explain_words(words: Sequence[WordScore]) -> list[WordScore]:
    """The same words with `feedback` set on every wrong phoneme. Scores are not touched."""
    return [
        word.model_copy(
            update={
                "phonemes": [
                    p.model_copy(update={"feedback": feedback_for(word.phonemes, i, word.text)})
                    for i, p in enumerate(word.phonemes)
                ]
            }
        )
        for word in words
    ]
