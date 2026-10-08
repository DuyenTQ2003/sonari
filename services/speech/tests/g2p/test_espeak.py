"""The en-gb reference from espeak-ng. The real-binary tests run in CI, which installs it."""

import os
import shutil

import pytest
from tests.scoring.fakes import fake_pronouncer

from sonari_speech.g2p.espeak import EspeakReference, EspeakUnavailable, parse_line
from sonari_speech.scoring.gop import load_vocab

needs_espeak = pytest.mark.skipif(
    shutil.which("espeak-ng") is None and not os.environ.get("CI"),
    reason="espeak-ng is not installed",
)


def test_a_line_becomes_tokens_without_stress_marks() -> None:
    vocab = set(load_vocab().ids)
    assert parse_line("f_ˈɔː", vocab) == ("f", "ɔː")
    assert parse_line("t_w_ˈɛ_n_t_i w_ˌɒ_n", vocab) == ("t", "w", "ɛ", "n", "t", "i", "w", "ɒ", "n")


def test_a_token_the_model_lacks_drops_the_word() -> None:
    assert parse_line("f_ˈɔː_Q!", set(load_vocab().ids)) is None
    assert parse_line("", set(load_vocab().ids)) is None


def test_a_missing_binary_is_reported_at_load() -> None:
    with pytest.raises(EspeakUnavailable):
        EspeakReference(set(), binary="no-such-espeak-ng")


@needs_espeak
def test_en_gb_is_non_rhotic_and_one_tuple_comes_back_per_word() -> None:
    words = fake_pronouncer().pronounce("one think you")
    british = EspeakReference(load_vocab().ids, voice="en-gb").tokens(words)
    assert british == [("w", "ɒ", "n"), ("θ", "ɪ", "ŋ", "k"), ("j", "uː")]


@needs_espeak
def test_en_gb_drops_the_r_that_en_us_keeps() -> None:
    from tests.g2p.fakes import FakeBackend

    from sonari_speech.g2p import Pronouncer

    words = Pronouncer(FakeBackend({"for": "F AO1 R"}), lexicon={}).pronounce("for")
    assert words[0].tokens == ("f", "ɔːɹ")
    assert EspeakReference(load_vocab().ids).tokens(words) == [("f", "ɔː")]
