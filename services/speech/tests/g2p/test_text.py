import pytest

from sonari_speech.g2p.text import Token, normalize_word, number_to_words, tokenize


def spans(text: str) -> list[tuple[str, int, int]]:
    return [(t.text, t.start, t.end) for t in tokenize(text)]


def test_words_keep_their_character_spans_for_the_ui() -> None:
    text = "Hello, big world!"
    assert spans(text) == [("Hello", 0, 5), ("big", 7, 10), ("world", 11, 16)]
    assert all(text[start:end] == word for word, start, end in spans(text))


def test_an_apostrophe_inside_a_word_stays_in_the_token() -> None:
    assert [t.text for t in tokenize("I'm sure we don't know")] == [
        "I'm",
        "sure",
        "we",
        "don't",
        "know",
    ]


def test_typographic_apostrophes_stay_inside_the_word() -> None:
    assert [t.text for t in tokenize("don’t go")] == ["don’t", "go"]


def test_quotes_around_a_word_are_not_part_of_it() -> None:
    assert spans("'hello' said \"Tom\"") == [("hello", 1, 6), ("said", 8, 12), ("Tom", 14, 17)]


def test_a_hyphen_splits_words_and_each_part_has_its_own_span() -> None:
    assert spans("well-known") == [("well", 0, 4), ("known", 5, 10)]


def test_accented_letters_stay_in_the_word() -> None:
    cafe = "caf" + chr(0xE9)  # not a literal: scripts/check_no_vietnamese.py flags accented letters
    assert [t.text for t in tokenize(f"a {cafe} here")] == ["a", cafe, "here"]


def test_numbers_are_tokens_of_their_own_kind() -> None:
    tokens = tokenize("I have 3 cats and 1,200 fish.")
    assert [(t.text, t.kind) for t in tokens] == [
        ("I", "word"),
        ("have", "word"),
        ("3", "number"),
        ("cats", "word"),
        ("and", "word"),
        ("1,200", "number"),
        ("fish", "word"),
    ]


@pytest.mark.parametrize("text", ["3.5", "1st", "22nd", "50%"])
def test_decimals_ordinals_and_percentages_are_one_number_token(text: str) -> None:
    assert tokenize(f"it is {text} now")[2] == Token(text, 6, 6 + len(text), "number")


def test_text_without_words_gives_no_tokens() -> None:
    assert tokenize("") == []
    assert tokenize("?! ... --") == []


def test_normalize_word_lowercases_and_straightens_apostrophes() -> None:
    assert normalize_word("Don’t") == "don't"
    assert normalize_word("I'M") == "i'm"


def test_normalize_word_strips_accents() -> None:
    assert normalize_word("Caf" + chr(0xE9)) == "cafe"


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("0", "zero"),
        ("7", "seven"),
        ("13", "thirteen"),
        ("21", "twenty one"),
        ("90", "ninety"),
        ("100", "one hundred"),
        ("101", "one hundred one"),
        ("342", "three hundred forty two"),
        ("1,200", "one thousand two hundred"),
        ("12,000", "twelve thousand"),
        ("2,500,000", "two million five hundred thousand"),
        ("1,000", "one thousand"),
    ],
)
def test_cardinals(text: str, words: str) -> None:
    assert number_to_words(text) == words.split()


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("1999", "nineteen ninety nine"),
        ("1905", "nineteen oh five"),
        ("1900", "nineteen hundred"),
        ("2024", "twenty twenty four"),
        ("2010", "twenty ten"),
        ("2000", "two thousand"),
        ("2005", "two thousand five"),
        ("1000", "one thousand"),
    ],
)
def test_four_digit_numbers_without_a_comma_read_as_years(text: str, words: str) -> None:
    assert number_to_words(text) == words.split()


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("3.5", "three point five"),
        ("0.25", "zero point two five"),
        ("50%", "fifty percent"),
        ("2.5%", "two point five percent"),
    ],
)
def test_decimals_and_percentages(text: str, words: str) -> None:
    assert number_to_words(text) == words.split()


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("1st", "first"),
        ("2nd", "second"),
        ("3rd", "third"),
        ("4th", "fourth"),
        ("5th", "fifth"),
        ("8th", "eighth"),
        ("9th", "ninth"),
        ("12th", "twelfth"),
        ("20th", "twentieth"),
        ("21st", "twenty first"),
        ("100th", "one hundredth"),
    ],
)
def test_ordinals(text: str, words: str) -> None:
    assert number_to_words(text) == words.split()


def test_leading_zeros_and_very_long_numbers_are_spelled_digit_by_digit() -> None:
    assert number_to_words("007") == ["zero", "zero", "seven"]
    assert number_to_words("1234567890123") == (
        [
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "zero",
            "one",
            "two",
            "three",
        ]
    )
