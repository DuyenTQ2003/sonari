import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.scoring.fakes import fake_pronouncer, posteriors
from tests.scoring.test_gop import SCHEMA, V0

from sonari_speech.scoring.contract import PhonemeVerdict, ScoreResponse, WordScore
from sonari_speech.scoring.feedback import (
    FALLBACK_KEY,
    KEY_PREFIX,
    Rule,
    explain_words,
    feedback_for,
    fold,
    load_table,
)
from sonari_speech.scoring.gop import load_vocab, score_words

VI_JSON = Path(__file__).resolve().parents[4] / "apps" / "web" / "messages" / "vi.json"
FIX = json.loads(VI_JSON.read_text("utf-8"))["pronunciation"]["fix"]
RULES = load_table().rules
PAIR_RULES = [r for r in RULES if r.heard is not None]
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# Letters that exist in Vietnamese and not in English or IPA (the pre-commit hook's idea).
VIETNAMESE = {
    *range(0x1EA0, 0x1EFA),
    0x0102,
    0x0103,
    0x0110,
    0x0111,
    0x01A0,
    0x01A1,
    0x01AF,
    0x01B0,
}


def verdicts(*phones: tuple[str, str | None]) -> list[PhonemeVerdict]:
    """One word: (expected, heard), heard None meaning said correctly."""
    return [
        PhonemeVerdict(
            expected=e,
            correct=h is None,
            heard=h,
            gop=1.0 if h is None else -1.0,
            start_ms=i * 20,
            end_ms=i * 20 + 20,
        )
        for i, (e, h) in enumerate(phones)
    ]


def key_of(*phones: tuple[str, str | None], at: int) -> str:
    result = feedback_for(verdicts(*phones), at, "word")
    assert result is not None
    return result.message_key.removeprefix(KEY_PREFIX)


# --- the table --------------------------------------------------------------------------


def test_every_rule_has_a_source_or_says_why_not() -> None:
    assert all(bool(r.sources) != bool(r.unsourced) for r in RULES)
    assert {s for r in RULES for s in r.sources} == set(load_table().sources)


def test_the_unsourced_pairs_are_the_ones_the_brief_asked_for_without_evidence() -> None:
    unsourced = {(r.expected[0], r.heard) for r in PAIR_RULES if r.unsourced and r.expected}
    assert unsourced == {("θ", "s"), ("ð", "d"), ("ʃ", "s")}


@pytest.mark.parametrize(
    "bad",
    [
        {"key": "k", "sources": ["a"]},  # neither heard nor position
        {"key": "k", "heard": "t", "position": "final", "expected": ["s"], "sources": ["a"]},
        {"key": "k", "heard": "t", "sources": ["a"]},  # a pair without `expected`
        {"key": "k", "position": "final"},  # no evidence and no reason
        {"key": "k", "position": "final", "sources": ["a"], "unsourced": "x"},
    ],
)
def test_a_malformed_rule_is_rejected_when_the_table_loads(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Rule.model_validate(bad)


# --- the copy lives in vi.json, one why and one how per key --------------------------------


def test_every_key_has_copy_and_every_copy_is_used() -> None:
    used = {r.key for r in RULES} | {FALLBACK_KEY}
    assert set(FIX) == used
    for key, text in FIX.items():
        assert set(text) == {"why", "how"}, key
        assert all(isinstance(t, str) and t.strip() for t in text.values()), key


def test_copy_only_uses_the_parameters_the_service_sends() -> None:
    sent = {"expected", "heard", "word"}
    for key, text in FIX.items():
        for line in text.values():
            assert set(PLACEHOLDER.findall(line)) <= sent, key
            assert "'" not in line, f"{key}: an ASCII apostrophe is an escape in ICU"
            assert "{" not in PLACEHOLDER.sub("", line), key


# --- lookup: every pair, the positions, the fallback -------------------------------------


@pytest.mark.parametrize("rule", PAIR_RULES, ids=lambda r: f"{r.expected}->{r.heard}")
def test_every_pair_in_the_table_gives_its_key(rule: Rule) -> None:
    assert rule.expected
    for expected in rule.expected:
        # Between two correct vowels: no cluster, not word-final.
        assert key_of(("ʌ", None), (expected, rule.heard), ("ʌ", None), at=1) == rule.key


@pytest.mark.parametrize(
    ("heard", "key"), [("tʰ", "th_stop"), ("t̪", "th_stop"), ("sʲ", "th_sibilant")]
)
def test_a_variant_of_the_heard_sound_counts_as_the_sound(heard: str, key: str) -> None:
    assert key_of(("ʌ", None), ("θ", heard), ("ʌ", None), at=1) == key


def test_fold_removes_aspiration_palatalisation_length_and_combining_marks() -> None:
    assert [fold(t) for t in ("tʰ", "sʲ", "iː", "t̪", "ɛ" + chr(0x303), "θ")] == [
        "t",
        "s",
        "i",
        "t",
        "ɛ",
        "θ",
    ]


def test_a_final_s_or_z_gets_the_sibilant_message_whatever_was_heard() -> None:
    assert key_of(("k", None), ("æ", None), ("t", None), ("s", "z"), at=3) == "final_sibilant"
    assert key_of(("d", None), ("ɔː", None), ("z", "ʌ"), at=2) == "final_sibilant"


def test_a_sibilant_that_is_not_final_does_not_get_it() -> None:
    assert key_of(("s", "t"), ("ɪ", None), ("t", None), at=0) != "final_sibilant"


def test_consonants_that_touch_get_the_cluster_message_a_lone_final_gets_the_final_one() -> None:
    street = (("s", "ʃ"), ("t", "k"), ("ɹ", "w"), ("iː", None), ("t", "p"))
    assert [key_of(*street, at=i) for i in (0, 1, 2)] == ["cluster"] * 3
    assert key_of(*street, at=4) == "final_consonant"


def test_a_vowel_that_ends_the_word_is_not_a_final_consonant() -> None:
    assert key_of(("k", None), ("ɑːɹ", "ʌ"), at=1) == FALLBACK_KEY
    assert key_of(("h", None), ("iː", "ɪ"), at=1) == FALLBACK_KEY


def test_a_pair_beats_a_position() -> None:
    assert key_of(("w", None), ("ɪ", None), ("θ", "t"), at=2) == "th_stop"


def test_a_pair_the_table_lacks_gets_the_generic_message_naming_the_sound() -> None:
    result = feedback_for(verdicts(("ʌ", None), ("k", "p"), ("ʌ", None)), 1, "cup")
    assert result is not None
    assert result.message_key == f"{KEY_PREFIX}{FALLBACK_KEY}"
    assert result.params.model_dump() == {"expected": "k", "heard": "p", "word": "cup"}


def test_the_direction_matters() -> None:
    assert key_of(("ʌ", None), ("t", "θ"), ("ʌ", None), at=1) == FALLBACK_KEY


def test_a_correct_phoneme_gets_no_feedback() -> None:
    assert feedback_for(verdicts(("θ", None)), 0, "think") is None


def test_params_carry_the_raw_heard_token_not_the_folded_one() -> None:
    result = feedback_for(verdicts(("ʌ", None), ("θ", "tʰ"), ("ʌ", None)), 1, "think")
    assert result is not None and result.params.heard == "tʰ"


# --- through scoring: nothing but `feedback` changes, and no Vietnamese leaves the service ---


def scored_think_said_as_tink() -> list[WordScore]:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("think you")  # θ ɪ ŋ k | j uː
    frames: list[str | None] = [None, "t", None, "ɪ", "ŋ", None, "k", None, "j", "uː", None]
    return score_words(words, posteriors(vocab, frames), 0.0, V0, vocab)


def test_explain_words_changes_only_the_feedback_of_wrong_phonemes() -> None:
    before = scored_think_said_as_tink()
    after = explain_words(before)
    for old, new in zip(before, after, strict=True):
        assert new.model_dump(exclude={"phonemes": {"__all__": {"feedback"}}}) == old.model_dump(
            exclude={"phonemes": {"__all__": {"feedback"}}}
        )
    wrong = [p for w in after for p in w.phonemes if not p.correct]
    assert [p.expected for p in wrong] == ["θ"]
    assert wrong[0].feedback is not None
    assert wrong[0].feedback.message_key == "pronunciation.fix.th_stop"
    assert all(p.feedback is None for w in after for p in w.phonemes if p.correct)


def test_the_response_with_feedback_matches_the_contract_and_holds_no_vietnamese() -> None:
    body = ScoreResponse(
        thresholds_version="v0",
        reference_text="think you",
        words=explain_words(scored_think_said_as_tink()),
    ).model_dump(mode="json", by_alias=True)
    Draft202012Validator(SCHEMA).validate(body)
    text = json.dumps(body, ensure_ascii=False)
    assert "pronunciation.fix.th_stop" in text
    assert not {ord(c) for c in text} & VIETNAMESE
    copy = [line for entry in FIX.values() for line in entry.values()]
    assert not any(line in text for line in copy)
