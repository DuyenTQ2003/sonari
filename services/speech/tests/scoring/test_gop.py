import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from tests.scoring.fakes import fake_pronouncer, posteriors

from sonari_speech.phoneset.mapping import mapped_tokens
from sonari_speech.scoring.contract import ScoreResponse
from sonari_speech.scoring.gop import (
    Thresholds,
    load_thresholds,
    load_vocab,
    phoneme_gops,
    score_words,
)

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[4] / "packages/contracts/schema/score-response.schema.json"
    ).read_text("utf-8")
)
V0 = Thresholds("test", 0.0)


def test_every_token_g2p_can_emit_is_in_the_model_vocab() -> None:
    assert mapped_tokens() <= set(load_vocab().ids)


def test_the_blank_and_special_tokens_never_compete() -> None:
    vocab = load_vocab()
    assert vocab.blank == 0
    assert len(vocab.ids) == 392
    assert {vocab.tokens[int(i)] for i in vocab.phonemes}.isdisjoint({"<s>", "<pad>", "</s>"})


def test_the_shipped_thresholds_say_they_are_uncalibrated() -> None:
    assert load_thresholds() == Thresholds("v0-uncalibrated", 0.0)


def test_a_phoneme_said_as_expected_scores_positive() -> None:
    vocab = load_vocab()
    gops = phoneme_gops(posteriors(vocab, [None, "θ", None, "ɪ", None]), ["θ", "ɪ"], vocab)
    assert [g.expected for g in gops] == ["θ", "ɪ"]
    assert all(g.gop > 0 for g in gops)
    assert [(g.start, g.end) for g in gops] == [(1, 2), (3, 4)]


def test_a_substituted_phoneme_scores_negative_and_names_what_was_heard() -> None:
    vocab = load_vocab()
    gops = phoneme_gops(posteriors(vocab, [None, "θ", None, "ɪ", None]), ["t", "ɪ"], vocab)
    assert gops[0].gop < 0
    assert gops[0].heard == "θ"
    assert gops[1].gop > 0


def test_words_group_their_phonemes_and_roll_up() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("think you")  # θ ɪ ŋ k | j uː
    frames: list[str | None] = [None, "t", None, "ɪ", "ŋ", None, "k", None, "j", "uː", None]
    scored = score_words(words, posteriors(vocab, frames), 0.5, V0, vocab)

    think, you = scored
    assert (think.text, think.start, think.end) == ("think", 0, 5)
    assert [(p.expected, p.correct, p.heard) for p in think.phonemes] == [
        ("θ", False, "t"),
        ("ɪ", True, None),
        ("ŋ", True, None),
        ("k", True, None),
    ]
    assert (think.correct, think.correct_phonemes) == (False, 3)
    assert (you.correct, you.correct_phonemes) == (True, 2)
    # Frame 1 of the trimmed audio is 20 ms after the speech start, which was 0.5 s in.
    assert (think.phonemes[0].start_ms, think.phonemes[0].end_ms) == (520, 540)


def test_the_threshold_decides_the_verdict() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("you")
    log_probs = posteriors(vocab, [None, "j", "uː", None])
    assert score_words(words, log_probs, 0.0, V0, vocab)[0].correct
    strict = Thresholds("strict", 100.0)
    assert not score_words(words, log_probs, 0.0, strict, vocab)[0].correct


@pytest.mark.parametrize("text", ["one think you", "took"])
def test_the_response_matches_the_contract_schema(text: str) -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce(text)
    tokens = [t for w in words for t in w.tokens]
    frames: list[str | None] = [x for t in tokens for x in (None, t)] + [None]
    scored = score_words(words, posteriors(vocab, frames), 0.0, V0, vocab)
    body = ScoreResponse(thresholds_version="v0", reference_text=text, words=scored)
    Draft202012Validator(SCHEMA).validate(body.model_dump(mode="json", by_alias=True))
