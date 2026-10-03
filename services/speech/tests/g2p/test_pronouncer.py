import time

import pytest
from tests.g2p.fakes import FakeBackend
from tests.g2p.words import WORDS

from sonari_speech.g2p.pronouncer import Pronouncer, WordPron


def make(
    dictionary: dict[str, str] | None = None,
    predictions: dict[str, str] | None = None,
    lexicon: dict[str, list[str]] | None = None,
) -> tuple[Pronouncer, FakeBackend]:
    backend = FakeBackend(dictionary, predictions)
    return Pronouncer(backend, lexicon={} if lexicon is None else lexicon), backend


def tokens(pron: WordPron) -> str:
    return " ".join(pron.tokens)


def test_there_are_at_least_thirty_words_under_test() -> None:
    assert len(WORDS) >= 30


@pytest.mark.parametrize(("word", "arpabet", "expected"), WORDS)
def test_dictionary_words_map_to_espeak_tokens(word: str, arpabet: str, expected: str) -> None:
    pronouncer, _ = make({word: arpabet})
    (pron,) = pronouncer.pronounce(word)
    assert tokens(pron) == expected
    assert pron.source == "dictionary"
    assert pron.arpabet == tuple(arpabet.split())


def test_each_word_keeps_its_span_in_the_original_text() -> None:
    pronouncer, _ = make({"the": "DH AH0", "car": "K AA1 R", "is": "IH1 Z", "near": "N IH1 R"})
    text = "The car is near."
    words = pronouncer.pronounce(text)
    assert [text[w.start : w.end] for w in words] == ["The", "car", "is", "near"]
    assert [w.text for w in words] == ["The", "car", "is", "near"]


def test_lookup_ignores_case_and_accents() -> None:
    pronouncer, _ = make({"think": "TH IH1 NG K", "cafe": "K AE0 F EY1"})
    assert tokens(pronouncer.pronounce("THINK")[0]) == "θ ɪ ŋ k"
    assert pronouncer.pronounce("caf" + chr(0xE9))[0].source == "dictionary"


def test_the_lexicon_overrides_the_dictionary() -> None:
    pronouncer, _ = make({"every": "EH1 V ER0 IY0"}, lexicon={"every": ["EH1", "V", "R", "IY0"]})
    (pron,) = pronouncer.pronounce("Every")
    assert tokens(pron) == "ɛ v ɹ i"
    assert pron.source == "lexicon"


def test_the_shipped_lexicon_is_used_by_default() -> None:
    pronouncer = Pronouncer(FakeBackend({"every": "EH1 V ER0 IY0"}))
    assert tokens(pronouncer.pronounce("every")[0]) == "ɛ v ɹ i"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("I'm", "aɪ m"), ("don't", "d oʊ n t"), ("Don’t", "d oʊ n t"), ("DON'T", "d oʊ n t")],
)
def test_contractions_in_the_dictionary_are_looked_up_whole(text: str, expected: str) -> None:
    pronouncer, backend = make({"i'm": "AY1 M", "don't": "D OW1 N T"})
    (pron,) = pronouncer.pronounce(text)
    assert tokens(pron) == expected
    assert pron.source == "dictionary"
    assert pron.text == text
    assert backend.predicted == []


def test_a_contraction_missing_from_the_dictionary_is_stem_plus_clitic() -> None:
    pronouncer, backend = make({"must": "M AH1 S T"})
    (pron,) = pronouncer.pronounce("mustn't")
    assert tokens(pron) == "m ʌ s t ə n t"
    assert pron.source == "contraction"
    assert backend.predicted == []


def test_the_stem_of_an_unknown_contraction_can_be_predicted() -> None:
    pronouncer, backend = make(predictions={"anna": "AE1 N AH0"})
    (pron,) = pronouncer.pronounce("Anna's")
    assert tokens(pron) == "æ n ə z"
    assert pron.source == "contraction"
    assert backend.predicted == ["anna"]


def test_an_unknown_word_is_predicted_and_invalid_phones_are_dropped() -> None:
    pronouncer, backend = make(predictions={"zorblat": "Z AO1 R B <unk> XY L AH0 T"})
    (pron,) = pronouncer.pronounce("zorblat")
    assert pron.source == "predicted"
    assert pron.arpabet == ("Z", "AO1", "R", "B", "L", "AH0", "T")
    assert backend.predicted == ["zorblat"]


def test_an_unknown_word_with_an_apostrophe_is_predicted_without_it() -> None:
    pronouncer, backend = make(predictions={"obrien": "OW0 B R AY1 AH0 N"})
    (pron,) = pronouncer.pronounce("O'Brien")
    assert pron.source == "predicted"
    assert backend.predicted == ["obrien"]


@pytest.mark.parametrize(
    ("text", "span", "expected"),
    [
        ("I have 3 cats", (7, 8), "θ ɹ iː"),
        ("It is 21 now", (6, 8), "t w ɛ n t i w ʌ n"),
        ("the 1st day", (4, 7), "f ɜː s t"),
    ],
)
def test_a_number_is_one_word_that_is_read_as_several(
    text: str, span: tuple[int, int], expected: str
) -> None:
    dictionary = {
        "three": "TH R IY1",
        "twenty": "T W EH1 N T IY0",
        "one": "W AH1 N",
        "first": "F ER1 S T",
    }
    pronouncer, _ = make(
        {**dictionary, **{w: "AH0" for w in ("i", "have", "cats", "it", "is", "now", "the", "day")}}
    )
    number = next(w for w in pronouncer.pronounce(text) if (w.start, w.end) == span)
    assert number.source == "number"
    assert tokens(number) == expected


def test_text_without_words_gives_nothing() -> None:
    pronouncer, _ = make()
    assert pronouncer.pronounce("") == []
    assert pronouncer.pronounce("?! ...") == []


def test_a_sentence_takes_well_under_ten_milliseconds() -> None:
    sentence = "I think the car is near the water and my family is happy about it."
    dictionary = {w: arpabet for w, arpabet, _ in WORDS}
    dictionary.update({w: "AH0" for w in ("i", "the", "is", "and", "my", "it")})
    pronouncer, _ = make(dictionary)
    timings = []
    for _ in range(20):
        start = time.perf_counter()
        pronouncer.pronounce(sentence)
        timings.append(time.perf_counter() - start)
    assert sorted(timings)[len(timings) // 2] < 0.010
