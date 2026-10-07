"""Speaking items: a practice sentence taken whole from a Source, with its expected phonemes.

ADR-0006: the sentence is the corpus's own, so an item records where in its Source it sits and
ingest (speaking_ingest.py) checks the Source still holds exactly that text. ADR-0010: it pins
one stored version of the passage (`Source._id`), never "current", so a re-trim cannot change
what an item says.
"""

from datetime import datetime
from typing import Self

from beanie import Document
from pydantic import BaseModel, Field, model_validator

MIN_WORDS, MAX_WORDS = 6, 14


class ItemWord(BaseModel):
    text: str
    start: int = Field(ge=0)  # character span in the sentence, for the UI
    end: int
    tokens: list[str] = Field(min_length=1)  # the espeak tokens the model should emit


class SpeakingItemRecord(BaseModel):
    """A line of the items file: everything that can be checked without a database."""

    source: str = Field(min_length=1)  # the pinned `Source._id`: voa:<article>@<rules_version>
    line: int = Field(ge=0)  # index into that Source's `text`
    start: int = Field(ge=0)  # offset of the sentence in that line
    unit: str = Field(min_length=1)
    text: str
    words: list[ItemWord]
    g2p_version: str = Field(min_length=1)  # which rules made `tokens`, so staleness shows

    @property
    def key(self) -> str:
        return f"{self.source}#{self.line}:{self.start}"

    @model_validator(mode="after")
    def _the_words_are_the_sentence(self) -> Self:
        if not MIN_WORDS <= len(self.words) <= MAX_WORDS:
            raise ValueError(f"{len(self.words)} words, outside {MIN_WORDS}-{MAX_WORDS}")
        if any(c.isdigit() for c in self.text):
            raise ValueError("the sentence has a digit: numbers are read several ways")
        for word in self.words:
            if self.text[word.start : word.end] != word.text:
                raise ValueError(f"word {word.text!r} is not at {word.start}-{word.end}")
        return self


class SpeakingItem(SpeakingItemRecord, Document):
    id: str  # type: ignore[assignment]  # `key`: deterministic, so a second run stores nothing
    ingested_at: datetime

    class Settings:
        # Nothing but `_id` is queried (20 documents), so nothing else is indexed.
        name = "speaking_items"
