import logging
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from tests.runtime.fakes import BlockingSession, FakeOrtSession
from tests.scoring.fakes import fake_pronouncer
from tests.support import needs_ffmpeg

from sonari_speech.main import create_app
from sonari_speech.runtime.model import ModelSession
from sonari_speech.runtime.service import SpeechRuntime
from sonari_speech.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"


def make_app(session: FakeOrtSession | None = None, **overrides: object) -> FastAPI:
    settings = Settings(cores=1, **overrides)  # type: ignore[arg-type]
    fake = session or FakeOrtSession()
    runtime = SpeechRuntime(settings, lambda _: ModelSession.from_session(fake))
    app = create_app(settings, runtime, fake_pronouncer)

    @app.post("/_test/analyse")  # stands in for /v1/score until P23
    async def analyse(request: Request) -> dict[str, float]:
        result = await runtime.analyse(await request.body())
        return {"speechS": result.speech_s, "frames": float(len(result.log_probs))}

    return app


def wait_until_ready(client: TestClient) -> None:
    deadline = time.monotonic() + 5
    while client.get("/readyz").status_code != 200:
        assert time.monotonic() < deadline, "never became ready"
        time.sleep(0.02)


def test_healthz_is_up_even_before_the_model_is_loaded() -> None:
    client = TestClient(make_app())  # no `with`: the lifespan, hence the load, never runs
    assert client.get("/healthz").json() == {"status": "ok", "service": "speech"}


def test_readyz_is_503_until_the_model_is_loaded() -> None:
    client = TestClient(make_app())
    response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "not_ready"
    assert body["messageKey"] == "errors.not_ready"
    assert body["details"]["checks"]["model"] == "down"


@needs_ffmpeg
def test_the_model_loads_in_the_background_and_readyz_turns_green() -> None:
    with TestClient(make_app()) as client:
        wait_until_ready(client)
        assert client.get("/readyz").json() == {
            "status": "ready",
            "checks": {"model": "ok", "g2p": "ok", "ffmpeg": "ok"},
        }


def test_readyz_is_503_when_ffmpeg_is_missing() -> None:
    with TestClient(make_app(ffmpeg_path="/nonexistent/ffmpeg")) as client:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = client.get("/readyz")
            if (
                response.json().get("error", {}).get("details", {}).get("checks", {}).get("model")
                == "ok"
            ):
                break
            time.sleep(0.02)
        checks = response.json()["error"]["details"]["checks"]
        assert response.status_code == 503
        assert checks == {"model": "ok", "g2p": "ok", "ffmpeg": "down"}


def test_a_model_that_fails_to_load_keeps_the_process_up_and_not_ready() -> None:
    settings = Settings(cores=1, model_dir=Path("/nonexistent"))
    app = create_app(settings, pronouncer_factory=fake_pronouncer)  # the real model loader
    with TestClient(app) as client:
        time.sleep(0.3)
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503


@needs_ffmpeg
def test_a_recording_goes_through_decode_trim_and_the_model() -> None:
    with TestClient(make_app()) as client:
        wait_until_ready(client)
        response = client.post("/_test/analyse", content=(FIXTURES / "ios.m4a").read_bytes())
        assert response.status_code == 200
        assert response.json()["speechS"] == pytest.approx(1.2, abs=0.12)


@needs_ffmpeg
def test_bad_audio_comes_back_as_an_error_envelope_with_a_message_key() -> None:
    with TestClient(make_app()) as client:
        wait_until_ready(client)
        response = client.post("/_test/analyse", content=b"this is not audio")
        assert response.status_code == 415
        assert response.json() == {
            "error": {
                "code": "audio_undecodable",
                "messageKey": "errors.audio.undecodable",
                "details": None,
            }
        }


@needs_ffmpeg
def test_when_full_the_service_answers_503_with_retry_after_instead_of_queueing() -> None:
    session = BlockingSession()
    with TestClient(make_app(session, max_in_flight=1, retry_after_s=3)) as client:
        wait_until_ready(client)
        session.close_gate()
        audio = (FIXTURES / "chrome.webm").read_bytes()
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(1) as pool:
            first = pool.submit(lambda: client.post("/_test/analyse", content=audio))
            assert session.entered.acquire(timeout=10)  # the first request is inside the model
            second = client.post("/_test/analyse", content=audio)
            assert second.status_code == 503
            assert second.headers["Retry-After"] == "3"
            assert second.json()["error"]["messageKey"] == "errors.speech.busy"
            session.release.set()
            assert first.result(timeout=10).status_code == 200


@needs_ffmpeg
def test_the_service_logs_its_capacity_at_info_level(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="sonari_speech")
    with TestClient(make_app()) as client:
        wait_until_ready(client)
    assert any(
        "cores=1 slots=1 in_flight_limit=2" in record.getMessage() for record in caplog.records
    )
    assert logging.getLogger("sonari_speech").handlers  # uvicorn would otherwise drop INFO
