"""ScoreResponse: the Pydantic side of packages/contracts/schema/score-response.schema.json.

A test validates what the service returns against that file, so the two cannot drift.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)


class PhonemeVerdict(_Camel):
    expected: str
    correct: bool
    heard: str | None  # the phoneme the model rated highest instead; None when correct
    gop: float
    start_ms: int
    end_ms: int


class WordScore(_Camel):
    text: str
    start: int
    end: int
    correct: bool
    correct_phonemes: int
    phonemes: list[PhonemeVerdict]


class ScoreResponse(_Camel):
    thresholds_version: str
    reference_text: str
    words: list[WordScore]
