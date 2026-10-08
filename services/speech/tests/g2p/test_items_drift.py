"""The expected phonemes stored with the practice sentences are what G2P gives today.

`tools/speaking_items/items.jsonl` holds each sentence's tokens, computed once so that the API
never recomputes them. If the lexicon, the ARPAbet-to-espeak table or g2p_en changes, this fails
until `make speaking-items` is run again and the file is reviewed.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from sonari_speech.g2p import Pronouncer
from sonari_speech.g2p.backend import default_nltk_dir, missing_nltk_data
from sonari_speech.g2p.version import g2p_version
from sonari_speech.scoring.contract import PhonemeVerdict
from sonari_speech.scoring.feedback import KEY_PREFIX, feedback_for, load_table

ITEMS = Path(__file__).resolve().parents[4] / "tools" / "speaking_items" / "items.jsonl"
RELIABLE = {"dictionary", "lexicon", "contraction"}  # what the picker accepts: not a guess

pytestmark = pytest.mark.skipif(
    bool(missing_nltk_data(default_nltk_dir())) and not os.environ.get("CI"),
    reason="NLTK data not found (see g2p/backend.py)",
)


def committed() -> list[dict[str, Any]]:
    return [json.loads(line) for line in ITEMS.read_text("utf-8").splitlines()]


def test_the_stored_phonemes_are_what_g2p_gives_today(real_pronouncer: Pronouncer) -> None:
    for item in committed():
        today = real_pronouncer.pronounce(item["text"])
        stored = [(w["text"], w["start"], w["end"], w["tokens"]) for w in item["words"]]
        assert stored == [(w.text, w.start, w.end, list(w.tokens)) for w in today], item["text"]


def test_no_stored_word_rests_on_a_g2p_guess(real_pronouncer: Pronouncer) -> None:
    for item in committed():
        guessed = [
            w.text for w in real_pronouncer.pronounce(item["text"]) if w.source not in RELIABLE
        ]
        assert guessed == [], item["text"]


def test_the_stored_g2p_version_is_the_current_one() -> None:
    assert {item["g2p_version"] for item in committed()} == {g2p_version()}


def test_the_sentences_can_show_every_rule_of_the_feedback_table() -> None:
    """Make each phoneme wrong in turn, with every sound a pair rule names and one none does."""
    heards = {r.heard for r in load_table().rules if r.heard} | {"?"}
    fired = set()
    for item in committed():
        for word in item["words"]:
            tokens = word["tokens"]
            for i, heard in ((i, h) for i in range(len(tokens)) for h in heards):
                verdicts = [
                    PhonemeVerdict(
                        expected=t,
                        verdict="correct" if j != i else "wrong",
                        heard=heard if j == i else None,
                        gop=0.0,
                        start_ms=0,
                        end_ms=0,
                    )
                    for j, t in enumerate(tokens)
                ]
                feedback = feedback_for(verdicts, i, word["text"])
                assert feedback is not None
                fired.add(feedback.message_key)
    assert {KEY_PREFIX + rule.key for rule in load_table().rules} <= fired
