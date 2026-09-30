"""Readability numbers and a coarse Sonari level for an inventory item.

The level is a sizing heuristic, not a CEFR model: P51 replaces it with a per-sentence
estimate. Let's Learn English lessons carry their level in the programme name. Every
other item is banded by Flesch-Kincaid grade, with thresholds fixed here before any
topic count was looked at.
"""

import re

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)]*\s+")
LESSON = re.compile(r"Let.s Learn English\s*-?\s*Level\s*(\d)", re.IGNORECASE)
# (upper bound of FK grade, level): B1 is level 4 on the Sonari scale (PLAN-v7 3.1).
FK_BANDS = ((7.0, 4), (9.0, 5), (11.0, 6))
TOP_LEVEL = 7


def syllables(word: str) -> int:
    w = word.lower().strip("'-’")
    count = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def stats(paragraphs: list[str]) -> tuple[int, float, float | None]:
    """(word count, mean words per sentence, Flesch-Kincaid grade or None if < 2 sentences)."""
    words = sum(len(WORD.findall(p)) for p in paragraphs)
    sentences = [s for p in paragraphs for s in SENTENCE_END.split(p.strip()) if WORD.search(s)]
    if not sentences or not words:
        return words, 0.0, None
    per_sentence = words / len(sentences)
    if len(sentences) < 2:
        return words, per_sentence, None
    syl = sum(syllables(w) for p in paragraphs for w in WORD.findall(p))
    return words, per_sentence, 0.39 * per_sentence + 11.8 * syl / words - 15.59


def estimate_level(program: str, fk_grade: float | None) -> int | None:
    lesson = LESSON.search(program)
    if lesson:
        return int(lesson.group(1))
    if fk_grade is None:
        return None
    return next((level for bound, level in FK_BANDS if fk_grade < bound), TOP_LEVEL)
