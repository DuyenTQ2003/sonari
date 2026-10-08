"""POST /v1/score wiring, on a fake model: shapes, errors and readiness, not accuracy."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from tests.runtime.fakes import FakeOrtSession
from tests.scoring.fakes import fake_british, fake_pronouncer
from tests.scoring.test_gop import SCHEMA
from tests.support import needs_ffmpeg

from sonari_speech.g2p import Pronouncer
from sonari_speech.g2p.espeak import EspeakUnavailable
from sonari_speech.main import create_app
from sonari_speech.runtime.model import ModelSession
from sonari_speech.runtime.service import SpeechRuntime
from sonari_speech.settings import Settings

AUDIO = (Path(__file__).parents[1] / "fixtures" / "ios.m4a").read_bytes()  # 1.2 s of "speech"


def make_app(pronouncer_factory: object = fake_pronouncer) -> FastAPI:
    settings = Settings(cores=1)
    runtime = SpeechRuntime(settings, lambda _: ModelSession.from_session(FakeOrtSession()))
    return create_app(settings, runtime, pronouncer_factory, fake_british)  # type: ignore[arg-type]


@contextmanager
def ready_client(app: FastAPI, timeout_s: float = 5) -> Iterator[TestClient]:
    with TestClient(app) as client:
        deadline = time.monotonic() + timeout_s
        while not (app.state.runtime.ready and app.state.scorer.ready):
            assert time.monotonic() < deadline, "never became ready"
            time.sleep(0.02)
        yield client


def post(client: TestClient, text: str, audio: bytes = AUDIO) -> dict:  # type: ignore[type-arg]
    response = client.post(
        "/v1/score", files={"audio": ("a.m4a", audio)}, data={"referenceText": text}
    )
    return {"status": response.status_code, **response.json()}


@needs_ffmpeg
def test_a_recording_and_a_sentence_give_one_verdict_per_phoneme() -> None:
    with ready_client(make_app()) as client:
        body = post(client, "One think you.")
    assert body.pop("status") == 200
    Draft202012Validator(SCHEMA).validate(body)
    assert body["thresholdsVersion"] == "v2-native-s20261008-val20261009"
    assert [w["text"] for w in body["words"]] == ["One", "think", "you"]
    assert [p["expected"] for p in body["words"][1]["phonemes"]] == ["θ", "ɪ", "ŋ", "k"]
    for word in body["words"]:
        for p in word["phonemes"]:
            assert (p["heard"] is None) == (p["verdict"] == "correct")
            assert (p["feedback"] is None) == (p["verdict"] != "wrong")
            assert p["startMs"] < p["endMs"] <= 2000


@needs_ffmpeg
def test_a_sentence_longer_than_the_speech_is_audio_too_short() -> None:
    with ready_client(make_app()) as client:
        body = post(client, " ".join(["think"] * 30))  # 120 phonemes in about 60 frames
    assert body["status"] == 422
    assert body["error"]["code"] == "audio_too_short"
    assert body["error"]["details"] == {"reason": "shorter_than_reference"}


def test_a_reference_with_no_pronounceable_word_is_a_validation_error() -> None:
    with ready_client(make_app()) as client:
        body = post(client, "...")
    assert body["status"] == 422
    assert body["error"]["code"] == "reference_unpronounceable"
    assert body["error"]["messageKey"] == "errors.validation"


def test_missing_fields_and_an_overlong_reference_are_validation_errors() -> None:
    with ready_client(make_app()) as client:
        no_text = client.post("/v1/score", files={"audio": ("a.m4a", AUDIO)})
        too_long = post(client, "think " * 60)
    assert no_text.status_code == 422
    assert no_text.json()["error"]["code"] == "validation_error"
    assert too_long["status"] == 422
    assert too_long["error"]["code"] == "validation_error"


def test_scoring_is_503_and_readyz_says_why_when_g2p_failed_to_load() -> None:
    def broken() -> Pronouncer:
        raise LookupError("cmudict missing")

    app = make_app(broken)
    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        while app.state.scorer.failure is None:
            assert time.monotonic() < deadline
            time.sleep(0.02)
        body = post(client, "think")
        checks = client.get("/readyz").json()["error"]["details"]["checks"]
    assert body["status"] == 503
    assert body["error"]["code"] == "not_ready"
    assert checks["g2p"] == "down"


@needs_ffmpeg
def test_a_failing_espeak_scores_en_us_only_instead_of_failing() -> None:
    class Broken:
        def tokens(self, words: object) -> list[None]:
            raise EspeakUnavailable("espeak-ng crashed")

    settings = Settings(cores=1)
    runtime = SpeechRuntime(settings, lambda _: ModelSession.from_session(FakeOrtSession()))
    app = create_app(settings, runtime, fake_pronouncer, Broken)  # type: ignore[arg-type]
    with ready_client(app) as client:
        body = post(client, "One think you.")
    assert body["status"] == 200
    assert {w["reference"] for w in body["words"]} == {"en-us"}
