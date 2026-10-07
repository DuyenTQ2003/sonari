"""The g2p_en backend. The live tests need NLTK data in DATA_DIR and skip without it."""

import os
import statistics
import time
from pathlib import Path

import nltk
import pytest
from tests.g2p.words import WORDS

from sonari_speech.g2p.backend import (
    REQUIRED,
    G2pDataMissing,
    G2pEnBackend,
    default_nltk_dir,
    missing_nltk_data,
    no_nltk_download,
)
from sonari_speech.g2p.pronouncer import Pronouncer, WordPron

DATA_DIR = default_nltk_dir()
# On a developer machine the tests of the real backend skip when the NLTK data is absent. In CI
# (`CI` is set) they run anyway and fail loudly: the workflow points DATA_DIR at the vendored copy
# in tests/data, so missing data there is a broken pipeline, and a skip would hide it.
needs_data = pytest.mark.skipif(
    bool(missing_nltk_data(DATA_DIR)) and not os.environ.get("CI"),
    reason=f"NLTK data not in {DATA_DIR} (see g2p/backend.py)",
)


def test_missing_nltk_data_lists_every_absent_resource(tmp_path: Path) -> None:
    assert missing_nltk_data(tmp_path) == list(REQUIRED)


def test_missing_nltk_data_finds_resources_in_the_directory(tmp_path: Path) -> None:
    for resource in REQUIRED:
        (tmp_path / resource).mkdir(parents=True)
    assert missing_nltk_data(tmp_path) == []


def test_no_nltk_download_disables_the_download_only_inside_the_block() -> None:
    original = nltk.download
    with no_nltk_download():
        assert nltk.download("cmudict") is False
    assert nltk.download is original


def test_the_backend_refuses_to_start_without_data_instead_of_downloading(tmp_path: Path) -> None:
    with pytest.raises(G2pDataMissing, match=r"sonari_speech\.g2p\.backend"):
        G2pEnBackend(tmp_path)


def test_the_default_data_dir_follows_data_dir_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", "/somewhere")
    assert default_nltk_dir() == Path("/somewhere/nltk_data")


@pytest.fixture(scope="module")
def pronouncer(real_pronouncer: Pronouncer) -> Pronouncer:
    return real_pronouncer


def tokens(pron: WordPron) -> str:
    return " ".join(pron.tokens)


@needs_data
@pytest.mark.parametrize(("word", "arpabet", "expected"), WORDS)
def test_real_g2p_gives_the_expected_tokens(
    pronouncer: Pronouncer, word: str, arpabet: str, expected: str
) -> None:
    (pron,) = pronouncer.pronounce(word)
    assert " ".join(pron.arpabet) == arpabet
    assert tokens(pron) == expected


@needs_data
def test_real_lexicon_words_use_the_override(pronouncer: Pronouncer) -> None:
    expected = {"every": "ɛ v ɹ i", "different": "d ɪ f ɹ ə n t", "camera": "k æ m ɹ ə"}
    for word, espeak in expected.items():
        (pron,) = pronouncer.pronounce(word)
        assert (pron.source, tokens(pron)) == ("lexicon", espeak)


@needs_data
def test_real_contractions(pronouncer: Pronouncer) -> None:
    got = {w.text: tokens(w) for w in pronouncer.pronounce("I'm sure he doesn't know, Anna's here")}
    assert got["I'm"] == "aɪ m"
    assert got["doesn't"] == "d ʌ z ə n t"
    assert got["Anna's"].endswith(" z")


@needs_data
def test_real_unknown_word_is_predicted(pronouncer: Pronouncer) -> None:
    (pron,) = pronouncer.pronounce("zorblat")
    assert pron.source == "predicted"
    assert pron.tokens


@needs_data
def test_a_real_sentence_takes_under_ten_milliseconds(pronouncer: Pronouncer) -> None:
    sentence = "I don't think the water in the restaurant is very good for my family, Zorblat."
    pronouncer.pronounce(sentence)  # warm up
    timings = []
    for _ in range(30):
        start = time.perf_counter()
        pronouncer.pronounce(sentence)
        timings.append(time.perf_counter() - start)
    assert statistics.median(timings) < 0.010
