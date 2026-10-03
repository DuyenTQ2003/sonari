"""Reference text -> word tokens with character spans, and digits -> spoken words.

Pure python, no dependencies. The spans index the ORIGINAL text so that the UI can
highlight the word that a phoneme belongs to. A number is one token (one UI word) even
though it is read as several words.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

# Letters of any script, minus digits and "_". An apostrophe between letters belongs to
# the word ("don't", "I'm"); quotes around a word do not.
_LETTERS = r"[^\W\d_]+"
_APOSTROPHES = "'\u2019\u02bc`"
_WORD = rf"{_LETTERS}(?:[{_APOSTROPHES}]{_LETTERS})*"
_NUMBER = r"\d+(?:,\d{3})*(?:\.\d+)?(?:(?:st|nd|rd|th)(?![^\W\d_])|%)?"
_TOKEN = re.compile(rf"(?P<number>{_NUMBER})|(?P<word>{_WORD})")
_PARSED_NUMBER = re.compile(
    r"(?P<int>\d+(?:,\d{3})*)(?:\.(?P<frac>\d+))?(?P<suffix>st|nd|rd|th|%)?"
)
_APOSTROPHE_TABLE = {ord(c): "'" for c in _APOSTROPHES}

_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = ("", "thousand", "million", "billion")
_MAX_CARDINAL_DIGITS = 12
_ORDINAL_IRREGULAR = {
    "one": "first",
    "two": "second",
    "three": "third",
    "five": "fifth",
    "eight": "eighth",
    "nine": "ninth",
    "twelve": "twelfth",
}


@dataclass(frozen=True, slots=True)
class Token:
    """A word or a number of the reference text; `text[start:end]` is `text` of the token."""

    text: str
    start: int
    end: int
    kind: Literal["word", "number"]


def tokenize(text: str) -> list[Token]:
    """Words and numbers of `text` in order, each with its span in `text`."""
    return [
        Token(m.group(), m.start(), m.end(), "number" if m.lastgroup == "number" else "word")
        for m in _TOKEN.finditer(text)
    ]


def normalize_word(word: str) -> str:
    """Lowercase, straight apostrophes, no accents: the key for dictionary lookups."""
    decomposed = unicodedata.normalize("NFD", word.translate(_APOSTROPHE_TABLE).lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def number_to_words(text: str) -> list[str]:
    """Spoken words of a number token: "1,200", "2024", "3.5", "1st", "50%".

    Four digits without a comma between 1100 and 2099 (2000-2009 excluded) read as a year
    ("1999" -> nineteen ninety nine, "2024" -> twenty twenty four); the comma form is a
    plain quantity. Leading zeros and numbers over 12 digits are spelled digit by digit.
    """
    parsed = _PARSED_NUMBER.fullmatch(text)
    if parsed is None:
        raise ValueError(f"not a number token: {text!r}")
    digits = parsed["int"].replace(",", "")
    suffix = parsed["suffix"]
    if parsed["frac"] is not None:
        words = [*_integer(digits, "," in parsed["int"]), "point", *_spell(parsed["frac"])]
    elif suffix in ("st", "nd", "rd", "th"):
        words = _integer(digits, plain=True)
        words[-1] = _ordinal(words[-1])
    else:
        words = _integer(digits, "," in parsed["int"])
    return [*words, "percent"] if suffix == "%" else words


def _integer(digits: str, plain: bool) -> list[str]:
    if (len(digits) > 1 and digits[0] == "0") or len(digits) > _MAX_CARDINAL_DIGITS:
        return _spell(digits)
    value = int(digits)
    if not plain and len(digits) == 4 and 1100 <= value <= 2099 and not 2000 <= value <= 2009:
        return _year(value)
    return _cardinal(value)


def _spell(digits: str) -> list[str]:
    return [_ONES[int(d)] for d in digits]


def _year(value: int) -> list[str]:
    high, low = divmod(value, 100)
    if low == 0:
        return [*_cardinal(high), "hundred"]
    if low < 10:
        return [*_cardinal(high), "oh", _ONES[low]]
    return [*_cardinal(high), *_cardinal(low)]


def _cardinal(value: int) -> list[str]:
    if value == 0:
        return ["zero"]
    groups: list[int] = []
    while value:
        value, group = divmod(value, 1000)
        groups.append(group)
    words: list[str] = []
    for scale, group in reversed(list(enumerate(groups))):
        if group:
            words += [*_below_thousand(group), *([_SCALES[scale]] if scale else [])]
    return words


def _below_thousand(value: int) -> list[str]:
    hundreds, rest = divmod(value, 100)
    words = [_ONES[hundreds], "hundred"] if hundreds else []
    if rest >= 20:
        tens, ones = divmod(rest, 10)
        words += [_TENS[tens], *([_ONES[ones]] if ones else [])]
    elif rest:
        words.append(_ONES[rest])
    return words


def _ordinal(word: str) -> str:
    if word in _ORDINAL_IRREGULAR:
        return _ORDINAL_IRREGULAR[word]
    return word[:-1] + "ieth" if word.endswith("y") else word + "th"
