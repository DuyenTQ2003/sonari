import numpy as np
import pytest
from audio_prep import expected_frames, greedy_ids, log_softmax, normalise
from bench_stats import burst_capacity, percentile, summarise


def test_normalise_gives_zero_mean_unit_variance_in_float32() -> None:
    rng = np.random.default_rng(0)
    out = normalise(rng.normal(3.0, 5.0, 16000).astype(np.float32))
    assert out.dtype == np.float32
    assert abs(out.mean()) < 1e-4
    assert abs(out.std() - 1.0) < 1e-3


def test_normalise_survives_silence() -> None:
    out = normalise(np.zeros(1600, dtype=np.float32))
    assert np.all(out == 0)


def test_log_softmax_matches_definition_and_is_stable() -> None:
    logits = np.array([[1000.0, 1001.0, 999.0]], dtype=np.float32)
    lp = log_softmax(logits)
    assert np.isfinite(lp).all()
    assert np.allclose(np.exp(lp).sum(axis=-1), 1.0, atol=1e-6)
    assert lp.argmax() == 1
    assert np.allclose(lp[0, 1] - lp[0, 0], 1.0, atol=1e-5)


def test_greedy_ids_collapses_repeats_and_drops_blanks() -> None:
    def onehot(ids: list[int]) -> np.ndarray:
        out = np.full((len(ids), 4), -10.0)
        out[np.arange(len(ids)), ids] = 0.0
        return out

    assert greedy_ids(onehot([0, 1, 1, 0, 2, 2, 0, 1]), blank=0) == [1, 2, 1]
    assert greedy_ids(onehot([0, 0, 0]), blank=0) == []
    assert greedy_ids(onehot([1, 0, 1]), blank=0) == [1, 1]  # a blank separates repeats


@pytest.mark.parametrize(
    ("samples", "frames"), [(16000 * 3, 149), (16000 * 8, 399), (12480, 38), (12160, 37)]
)
def test_expected_frames_matches_the_model_output_lengths(samples: int, frames: int) -> None:
    # The four values were observed from the real model in P04 (3 s, 8 s and the G0 clips).
    assert expected_frames(samples) == frames


def test_percentile_and_summary() -> None:
    xs = [float(x) for x in range(1, 101)]
    assert percentile(xs, 50) == pytest.approx(50.5)
    s = summarise(xs)
    assert s["n"] == 100 and s["min_ms"] == 1.0 and s["max_ms"] == 100.0
    assert s["p95_ms"] == pytest.approx(95.05, abs=0.1)


@pytest.mark.parametrize(
    ("service_ms", "cores", "expected"),
    [(1350, 1, 1), (1350, 4, 4), (620, 1, 3), (620, 4, 12), (2500, 2, 0)],
)
def test_burst_capacity_arithmetic(service_ms: float, cores: int, expected: int) -> None:
    assert burst_capacity(service_ms, cores) == expected
