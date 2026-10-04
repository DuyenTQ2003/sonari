"""Models of the content database: the validated passage, and the Beanie document that stores it."""

from datetime import datetime
from typing import ClassVar, Self

from beanie import Document
from pydantic import BaseModel, Field, model_validator
from pymongo import ASCENDING, IndexModel


class RemovedLine(BaseModel):
    """One line a trim took out of the original (ADR-0008 decision 3)."""

    index: int  # 0-based, into `original_text`
    kind: str = Field(min_length=1)
    rule: str = Field(min_length=1)  # the rule that removed it, so a reader can audit the call
    text: str


class Trim(BaseModel):
    rules_version: str = Field(min_length=1)
    cap: float  # the most the trim was allowed to cut, as a share of the original's words
    removed_words: int  # editorial words only; page furniture does not count against the cap
    removed_share: float
    removed: list[RemovedLine]


class TrimmedPassage(BaseModel):
    """One passage of English source text as one rules version trimmed it.

    This is a line of the trimmed corpus, checked the way ADR-0008 asks: a trim removes whole
    lines and nothing else. It needs no database, so a file is validated before anything is
    written. `Source` is the stored form.
    """

    source_id: str  # `voa:<article number>`: the passage, whatever version of its trim this is
    url: str
    title: str
    program: str = ""  # empty when the page names none
    fk: float  # Flesch-Kincaid grade of `text`, the trimmed lines
    original_words: int  # editorial words of the ORIGINAL; the denominator of `trim.removed_share`
    original_text: list[str]  # the lines as the parser returned them, untouched
    text: list[str]  # `original_text` minus `trim.removed`, byte for byte
    trim: Trim

    @property
    def key(self) -> str:
        """Identity of this version of the passage: also its `_id` once stored (ADR-0010)."""
        return f"{self.source_id}@{self.trim.rules_version}"

    @model_validator(mode="after")
    def _text_is_the_original_minus_the_removed_lines(self) -> Self:
        gone = [line.index for line in self.trim.removed]
        if len(set(gone)) != len(gone):
            raise ValueError("a line is recorded as removed twice")
        for line in self.trim.removed:
            if not 0 <= line.index < len(self.original_text):
                raise ValueError(f"removed index {line.index} is outside the original")
            if self.original_text[line.index] != line.text:
                raise ValueError(f"removed line {line.index} is not the original line")
        kept = [text for index, text in enumerate(self.original_text) if index not in set(gone)]
        if self.text != kept:
            raise ValueError("text is not the original lines minus the removed ones")
        if self.trim.removed_share > self.trim.cap:
            raise ValueError(
                f"the trim cut {self.trim.removed_share} of the words, over its cap {self.trim.cap}"
            )
        return self


class Source(TrimmedPassage, Document):
    """A stored version of a passage. Every rules version is its own immutable document;
    exactly one version of a passage is `current` (ADR-0010). Everything downstream reads
    `text`; `original_text` and `trim` let the trim be audited and undone."""

    id: str  # type: ignore[assignment]  # `key`, so dev and prod hold the same ids
    current: bool
    ingested_at: datetime

    class Settings:
        name = "sources"
        # The one query that needs an index: "the current version of this passage". The
        # partial unique index is also what guarantees there is never a second one.
        # `_id` serves lookups of a pinned version. Nothing else is indexed: a filter on `fk`
        # or `original_words` scans a few hundred current sources faster than an index pays.
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel(
                [("source_id", ASCENDING)],
                name="source_id_current",
                unique=True,
                partialFilterExpression={"current": True},
            )
        ]

    @classmethod
    async def get_current(cls, source_id: str) -> Self | None:
        return await cls.find_one({"source_id": source_id, "current": True})
