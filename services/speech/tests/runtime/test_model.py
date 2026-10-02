import time
from pathlib import Path

import numpy as np
import pytest
from tests.runtime.fakes import VOCAB, FakeOrtSession

from sonari_speech.runtime.model import (
    FRAME_S,
    ModelSession,
    expected_frames,
    log_softmax,
    normalise,
)
from sonari_speech.runtime.weights import DEFAULT_MODEL, is_valid, load_manifest
from sonari_speech.settings import Settings


def test_normalise_gives_zero_mean_and_unit_variance() -> None:
    audio = np.random.default_rng(0).normal(0.3, 0.05, 16000).astype(np.float32)
    out = normalise(audio)
    assert out.dtype == np.float32
    assert float(out.mean()) == pytest.approx(0.0, abs=1e-4)
    assert float(out.std()) == pytest.approx(1.0, abs=1e-3)


def test_normalise_of_a_constant_clip_is_zeros_not_nan() -> None:
    out = normalise(np.full(16000, 0.2, dtype=np.float32))
    assert np.isfinite(out).all()
    assert float(np.abs(out).max()) < 1e-3


def test_log_softmax_rows_are_log_probabilities_even_for_huge_logits() -> None:
    logits = np.array([[1000.0, 1001.0, 999.0], [-1000.0, 0.0, 1000.0]], dtype=np.float32)
    out = log_softmax(logits)
    assert out.dtype == np.float32
    assert np.isfinite(out).all()
    assert np.exp(out).sum(axis=-1) == pytest.approx([1.0, 1.0], abs=1e-6)
    assert out.argmax(axis=-1).tolist() == [1, 2]


@pytest.mark.parametrize(("samples", "frames"), [(400, 1), (16000, 49), (48000, 149)])
def test_expected_frames_follows_the_wav2vec2_conv_stack(samples: int, frames: int) -> None:
    assert expected_frames(samples) == frames


def test_frame_length_is_twenty_milliseconds() -> None:
    assert pytest.approx(0.02) == FRAME_S


def test_infer_returns_log_posteriors_per_frame() -> None:
    fake = FakeOrtSession()
    model = ModelSession.from_session(fake)
    audio = np.random.default_rng(1).normal(0, 0.1, 16000).astype(np.float32)
    out = model.infer(audio)
    assert out.shape == (49, VOCAB)
    assert out.dtype == np.float32
    assert np.exp(out).sum(axis=-1) == pytest.approx(np.ones(49), abs=1e-5)
    assert fake.feeds[0].shape == (1, 16000)  # a batch of one
    assert float(fake.feeds[0].mean()) == pytest.approx(0.0, abs=1e-4)  # fed normalised


def test_infer_rejects_audio_too_short_for_one_frame() -> None:
    with pytest.raises(ValueError, match="400"):
        ModelSession.from_session(FakeOrtSession()).infer(np.zeros(399, dtype=np.float32))


def test_warmup_runs_one_inference_and_returns_its_duration() -> None:
    fake = FakeOrtSession()
    seconds = ModelSession.from_session(fake).warmup()
    assert len(fake.feeds) == 1
    assert 0.0 <= seconds < 5.0


# --- the real int8 model: skipped when the file is not on this machine --------------------

MODEL_PATH = Settings().model_path
needs_model = pytest.mark.skipif(not MODEL_PATH.exists(), reason=f"{MODEL_PATH} not found")


@pytest.fixture(scope="module")
def real() -> ModelSession:
    return ModelSession.load(MODEL_PATH, intra_op_threads=1)


@needs_model
def test_the_local_model_file_is_the_pinned_one() -> None:
    assert is_valid(MODEL_PATH, load_manifest()[DEFAULT_MODEL])


@needs_model
def test_the_real_model_gives_392_way_log_posteriors_per_frame(real: ModelSession) -> None:
    audio = np.random.default_rng(2).normal(0, 0.1, 24000).astype(np.float32)  # 1.5 s
    out = real.infer(audio)
    assert out.shape == (expected_frames(24000), VOCAB)
    assert np.isfinite(out).all()
    assert np.exp(out).sum(axis=-1) == pytest.approx(np.ones(len(out)), abs=1e-4)


@needs_model
def test_the_real_model_is_deterministic(real: ModelSession) -> None:
    audio = np.random.default_rng(3).normal(0, 0.1, 16000).astype(np.float32)
    assert np.array_equal(real.infer(audio), real.infer(audio))


@needs_model
def test_the_real_model_warms_up_quickly(real: ModelSession) -> None:
    start = time.perf_counter()
    real.warmup()
    assert time.perf_counter() - start < 5.0


def test_load_of_a_missing_file_says_which_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"nope\.onnx"):
        ModelSession.load(tmp_path / "nope.onnx", intra_op_threads=1)
