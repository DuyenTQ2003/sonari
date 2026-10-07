"""The real pipeline (int8 model, g2p_en, ffmpeg) on the G0 clips, through POST /v1/score.

Skipped when the model or the clips are not on this machine: no audio is committed and CI
does not fetch the model. The clips are LibriSpeech dev-clean (CC BY 4.0), cut by
tools/evaldata/build_g0.py into DATA_DIR/derived/g0/. Both are ONE NATIVE SPEAKER reading
correctly; neither is a learner error:

    good.wav   "... one think you"          (contains /θ/)
    bad.wav    "... and took his dead"      (contains /t/; "dead" is cut at the clip end)

So "mostly wrong" is shown two ways that are honest about it: a clip scored against a
sentence it does not say, and a single phoneme substituted in the reference (P02's
θ <-> t). Neither is evidence about Vietnamese speakers; that is gate G1.

See every phoneme with `pytest -rP tests/scoring/test_g0_clips.py`.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.scoring.test_api import ready_client
from tests.support import needs_ffmpeg

from sonari_speech.g2p import Pronouncer
from sonari_speech.main import create_app
from sonari_speech.runtime.model import ModelSession
from sonari_speech.runtime.service import SpeechRuntime
from sonari_speech.settings import Settings

G0 = Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser() / "derived" / "g0"
SETTINGS = Settings(cores=1)

pytestmark = [
    needs_ffmpeg,
    pytest.mark.skipif(not SETTINGS.model_path.exists(), reason="int8 model not on this machine"),
    pytest.mark.skipif(not (G0 / "good.wav").exists(), reason=f"G0 clips not in {G0}"),
]


@pytest.fixture(scope="module")
def client(real_model: ModelSession, real_pronouncer: Pronouncer) -> Iterator[TestClient]:
    runtime = SpeechRuntime(SETTINGS, lambda _: real_model)
    app = create_app(SETTINGS, runtime, lambda: real_pronouncer)
    with ready_client(app, timeout_s=60) as client:
        yield client


def score(client: TestClient, clip: str, text: str) -> list[dict[str, Any]]:
    """POST the clip, print the per-phoneme table, return the phonemes in order."""
    audio = (G0 / clip).read_bytes()
    response = client.post(
        "/v1/score", files={"audio": (clip, audio)}, data={"referenceText": text}
    )
    assert response.status_code == 200, response.text
    phonemes = []
    print(f"\n{clip} scored as {text!r}")
    for word in response.json()["words"]:
        for p in word["phonemes"]:
            phonemes.append(p)
            verdict = "ok" if p["correct"] else f"WRONG, heard {p['heard']}"
            print(
                f"  {word['text']:<6} /{p['expected']}/  gop {p['gop']:>7.2f}  "
                f"{p['startMs']:>4}-{p['endMs']:<4} ms  {verdict}"
            )
    print(f"  correct: {share_correct(phonemes):.0%} of {len(phonemes)}")
    return phonemes


def share_correct(phonemes: list[dict[str, Any]]) -> float:
    return sum(p["correct"] for p in phonemes) / len(phonemes)


def test_good_wav_against_what_it_says_is_mostly_correct(client: TestClient) -> None:
    phonemes = score(client, "good.wav", "one think you")
    assert share_correct(phonemes) >= 0.8
    assert phonemes[3]["expected"] == "θ" and phonemes[3]["correct"]


def test_bad_wav_against_what_it_says_is_mostly_correct_too(client: TestClient) -> None:
    # A native reading; the misses are "and" read strong (æ) against the weak form ə, and
    # "dead" cut off by the clip edge.
    assert share_correct(score(client, "bad.wav", "and took his dead")) >= 0.6


def test_bad_wav_against_a_sentence_it_does_not_say_is_mostly_wrong(client: TestClient) -> None:
    assert share_correct(score(client, "bad.wav", "one think you")) <= 0.4


@pytest.mark.parametrize(
    ("clip", "text", "index", "expected", "heard"),
    [
        ("good.wav", "one tink you", 3, "t", "θ"),  # P02's gate case, now in a sentence
        ("bad.wav", "and thook his dead", 3, "θ", "t"),  # P02's misplaced case, now placed
    ],
)
def test_a_substituted_phoneme_is_wrong_names_what_was_said_and_nothing_else_moves(
    client: TestClient, clip: str, text: str, index: int, expected: str, heard: str
) -> None:
    substituted = score(client, clip, text)
    original = score(client, clip, text.replace("tink", "think").replace("thook", "took"))
    assert substituted[index]["expected"] == expected
    assert not substituted[index]["correct"]
    assert substituted[index]["heard"] == heard
    # "thook" is not in CMUdict and g2p_en guesses /uː/ for its vowel: compare like with like.
    pairs = zip(substituted, original, strict=True)
    moved = [i for i, (s, o) in enumerate(pairs) if s["expected"] == o["expected"] and s != o]
    assert moved == []
