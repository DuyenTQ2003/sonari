import asyncio
from pathlib import Path

import numpy as np
import pytest
from tests.runtime.fakes import VOCAB, BlockingSession, FakeOrtSession
from tests.support import needs_ffmpeg

from sonari_speech.errors import AppError, MessageKey
from sonari_speech.runtime.gate import Overloaded
from sonari_speech.runtime.model import ModelSession, expected_frames
from sonari_speech.runtime.service import SpeechRuntime, load_pinned_model
from sonari_speech.runtime.weights import WeightsError
from sonari_speech.settings import Settings

FIXTURES = Path(__file__).parents[1] / "fixtures"


def runtime_with(session: FakeOrtSession, **overrides: object) -> SpeechRuntime:
    settings = Settings(cores=1, **overrides)  # type: ignore[arg-type]
    return SpeechRuntime(settings, lambda _: ModelSession.from_session(session))


async def test_the_runtime_is_not_ready_until_it_has_loaded_and_warmed_up() -> None:
    session = FakeOrtSession()
    runtime = runtime_with(session)
    assert runtime.ready is False
    await runtime.start()
    assert runtime.ready is True
    assert len(session.feeds) == 1  # the warm-up inference ran before it turned ready


async def test_a_failed_load_is_recorded_and_the_runtime_stays_not_ready() -> None:
    def broken(_: Settings) -> ModelSession:
        raise WeightsError("checksum mismatch")

    runtime = SpeechRuntime(Settings(cores=1), broken)
    await runtime.start()  # does not raise: the process stays up and /readyz says why
    assert runtime.ready is False
    assert "checksum mismatch" in (runtime.failure or "")


async def test_analyse_before_the_model_is_ready_is_a_503_with_retry_after() -> None:
    runtime = runtime_with(FakeOrtSession())
    with pytest.raises(AppError) as err:
        await runtime.analyse(b"anything")
    assert err.value.status_code == 503
    assert err.value.message_key is MessageKey.NOT_READY
    assert err.value.headers == {"Retry-After": "2"}


@needs_ffmpeg
async def test_analyse_decodes_trims_and_returns_log_posteriors() -> None:
    runtime = runtime_with(FakeOrtSession())
    await runtime.start()
    result = await runtime.analyse((FIXTURES / "chrome.webm").read_bytes())
    # the fixture is 0.4 s of floor noise, 1.2 s of tone, 0.4 s of floor noise
    assert result.speech_start_s == pytest.approx(0.4, abs=0.08)
    assert result.speech_s == pytest.approx(1.2, abs=0.12)
    assert result.total_s == pytest.approx(2.0, abs=0.05)
    assert result.log_probs.shape == (expected_frames(len(result.samples)), VOCAB)
    assert len(result.samples) / 16000 < result.total_s  # the silence was cut off


@needs_ffmpeg
async def test_a_recording_with_no_speech_is_rejected_as_too_short(tmp_path: Path) -> None:
    import wave

    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        noise = np.random.default_rng(0).normal(0, 3, 32000).astype("<i2")
        out.writeframes(noise.tobytes())
    runtime = runtime_with(FakeOrtSession())
    await runtime.start()
    with pytest.raises(AppError) as err:
        await runtime.analyse(path.read_bytes())
    assert err.value.message_key is MessageKey.AUDIO_TOO_SHORT
    assert err.value.status_code == 422


@needs_ffmpeg
async def test_requests_beyond_the_capacity_get_503_while_the_model_is_busy() -> None:
    session = BlockingSession()
    runtime = runtime_with(session, max_in_flight=1)  # one slot, none waiting
    await runtime.start()
    session.close_gate()
    audio = (FIXTURES / "chrome.webm").read_bytes()
    first = asyncio.create_task(runtime.analyse(audio))
    assert await asyncio.to_thread(session.entered.acquire, True, 10)  # the first is inside
    with pytest.raises(Overloaded) as err:
        await runtime.analyse(audio)
    assert err.value.headers == {"Retry-After": "2"}
    session.release.set()
    assert (await first).log_probs.shape[1] == VOCAB


@needs_ffmpeg
async def test_no_more_than_the_slots_run_the_model_at_once() -> None:
    session = BlockingSession()
    settings = Settings(cores=2, max_in_flight=5)
    runtime = SpeechRuntime(settings, lambda _: ModelSession.from_session(session))
    await runtime.start()
    session.close_gate()
    audio = (FIXTURES / "chrome.webm").read_bytes()
    tasks = [asyncio.create_task(runtime.analyse(audio)) for _ in range(4)]
    for _ in range(2):
        assert await asyncio.to_thread(session.entered.acquire, True, 10)
    await asyncio.sleep(0.2)  # give a third request every chance to sneak in
    assert session.peak == 2
    session.release.set()
    await asyncio.gather(*tasks)
    assert session.peak == 2


def test_load_pinned_model_refuses_a_file_that_is_not_the_pinned_one(tmp_path: Path) -> None:
    (tmp_path / "wav2vec2_int8.onnx").write_bytes(b"not the model")
    with pytest.raises(WeightsError):
        load_pinned_model(Settings(model_dir=tmp_path))


def wav_with_a_burst(burst_s: float, tmp_path: Path) -> bytes:
    """0.6 s of low noise, `burst_s` of loud noise, 0.6 s of low noise, as 16 kHz WAV."""
    import wave

    rng = np.random.default_rng(5)
    parts = [
        rng.normal(0, 0.0005, 9600),
        rng.normal(0, 0.1, int(burst_s * 16000)),
        rng.normal(0, 0.0005, 9600),
    ]
    path = tmp_path / "burst.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes((np.concatenate(parts) * 32767).astype("<i2").tobytes())
    return path.read_bytes()


@needs_ffmpeg
@pytest.mark.parametrize(
    ("burst_s", "accepted"), [(0.2, False), (0.28, False), (0.4, True), (1.0, True)]
)
async def test_the_speech_minimum_is_a_third_of_a_second(
    burst_s: float, accepted: bool, tmp_path: Path
) -> None:
    runtime = runtime_with(FakeOrtSession())
    await runtime.start()
    data = wav_with_a_burst(burst_s, tmp_path)
    if accepted:
        assert (await runtime.analyse(data)).speech_s == pytest.approx(burst_s, abs=0.06)
    else:
        with pytest.raises(AppError) as err:
            await runtime.analyse(data)
        assert err.value.message_key is MessageKey.AUDIO_TOO_SHORT
