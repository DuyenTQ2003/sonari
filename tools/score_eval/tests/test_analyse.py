"""Verdicts, the per-word accent choice (as scoring/accents.py), the v2 search, collapse."""

from typing import Any

import pytest
from score_eval.analyse import (
    choose,
    collapse,
    per_clip,
    propose,
    verdict,
    wrong_share,
)
from score_eval.native import sample


def ph(gop: float, expected: str = "x") -> dict[str, Any]:
    return {"expected": expected, "gop": gop, "heard": "y"}


def word(us: list[float], gb: list[float] | None = None, text: str = "w") -> dict[str, Any]:
    british = None if gb is None else [ph(g) for g in gb]
    return {"text": text, "us": [ph(g) for g in us], "gb": british}


def clip(*words: dict[str, Any], cid: str = "c", speaker: str = "s") -> dict[str, Any]:
    return {"id": cid, "speaker": speaker, "words": list(words)}


def test_three_verdicts_split_as_the_service_does() -> None:
    assert [verdict(g, -3.4) for g in (0.01, 0.0, -3.4, -3.41)] == [
        "correct",
        "unclear",
        "unclear",
        "wrong",
    ]


def test_the_accent_with_fewer_wrong_then_fewer_unclear_then_higher_mean_wins() -> None:
    assert choose(word([1.0, -5.0], [1.0, -1.0]), -3.4)[0] == "en-gb"  # fewer wrong
    assert choose(word([1.0, -1.0], [1.0, 1.0]), -3.4)[0] == "en-gb"  # fewer unclear
    assert choose(word([1.0, 2.0], [1.0, 3.0]), -3.4)[0] == "en-gb"  # higher mean
    assert choose(word([1.0, 3.0], [1.0, 3.0]), -3.4)[0] == "en-us"  # a tie keeps en-us
    assert choose(word([-5.0]), -3.4)[0] == "en-us"  # no British form


def test_the_choice_depends_on_the_threshold() -> None:
    w = word([-5.0, 4.0], [-4.0, -4.0])  # us mean -0.5, gb mean -4
    assert choose(w, -3.4)[0] == "en-us"  # 1 wrong vs 2
    assert choose(w, -6.0)[0] == "en-us"  # 0 vs 0 wrong, 1 vs 2 unclear


def test_propose_finds_the_highest_threshold_under_the_target() -> None:
    clips = [clip(word([-5.0] + [3.0] * 199))]  # 0.5% at -5
    assert propose(clips, target=0.01) == -3.4
    clips = [clip(word([-5.0, -6.0, -8.0] + [3.0] * 97))]  # 3% below -3.4
    t = propose(clips, target=0.01)
    assert wrong_share(clips, t) < 0.01
    assert wrong_share(clips, round(t + 0.1, 1)) >= 0.01
    assert t == -8.0


def test_per_clip_counts_clips_with_no_wrong_too() -> None:
    clips = [clip(word([-5.0]), cid="a"), clip(word([2.0]), cid="b")]
    assert per_clip(clips, -3.4) == {"a": 1, "b": 0}


def test_collapse_counts_words_where_most_phonemes_fail() -> None:
    c = clip(
        word([-5.0, -6.0, 2.0], text="valued"),  # 2 of 3: collapsed
        word([-5.0, 2.0, 2.0], text="for"),  # 1 of 3: not
        word([-9.0], text="a"),  # one phoneme: never counted
    )
    found = collapse([c], -3.4)
    assert (found.observed, found.wrong_in_collapsed, found.wrong) == (1, 2, 4)
    p = 4 / 7  # the overall wrong rate of this clip; two words of 3 phonemes can collapse
    assert found.expected == pytest.approx(2 * (3 * p**2 * (1 - p) + p**3))


def test_the_sample_is_fixed_by_the_seed_and_respects_the_length_cap() -> None:
    index = [{"utterance_id": f"u{i:03}", "duration": float(i % 20)} for i in range(300)]
    first = sample(index, 50, 15.0, seed=1)
    assert first == sample(list(reversed(index)), 50, 15.0, seed=1)
    assert all(r["duration"] <= 15.0 for r in first)
    with pytest.raises(ValueError):
        sample(index, 1000, 15.0, seed=1)
