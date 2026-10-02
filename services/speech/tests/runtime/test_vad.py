import numpy as np
import pytest

from sonari_speech.runtime.vad import SAMPLE_RATE, trim_silence

RNG = np.random.default_rng(7)


def noise(seconds: float, dbfs: float) -> np.ndarray:
    """White noise whose RMS is `dbfs` below full scale."""
    return (RNG.normal(0.0, 10 ** (dbfs / 20), int(seconds * SAMPLE_RATE))).astype(np.float32)


def clip(*parts: np.ndarray) -> np.ndarray:
    return np.concatenate(parts)


def seconds(samples: np.ndarray) -> float:
    return len(samples) / SAMPLE_RATE


def test_leading_and_trailing_silence_is_trimmed_but_a_pad_is_kept() -> None:
    audio = clip(noise(0.6, -65), noise(1.0, -20), noise(0.8, -65))
    result = trim_silence(audio, pad_s=0.15)
    assert result.start_s == pytest.approx(0.6, abs=0.04)
    assert result.end_s == pytest.approx(1.6, abs=0.04)
    assert result.speech_s == pytest.approx(1.0, abs=0.06)
    assert seconds(result.samples) == pytest.approx(1.0 + 2 * 0.15, abs=0.06)


def test_the_pad_never_reaches_past_the_ends_of_the_clip() -> None:
    audio = clip(noise(0.05, -65), noise(0.5, -20), noise(0.05, -65))
    result = trim_silence(audio, pad_s=0.15)
    assert len(result.samples) <= len(audio)
    assert seconds(result.samples) == pytest.approx(0.6, abs=0.04)


def test_a_pause_inside_the_speech_is_kept() -> None:
    audio = clip(
        noise(0.4, -65), noise(0.5, -20), noise(0.5, -65), noise(0.5, -20), noise(0.4, -65)
    )
    result = trim_silence(audio, pad_s=0.0)
    assert seconds(result.samples) == pytest.approx(1.5, abs=0.06)
    assert result.speech_s == pytest.approx(1.5, abs=0.06)


@pytest.mark.parametrize("level", [-90.0, -65.0, -45.0])
def test_a_clip_with_only_background_noise_has_no_speech(level: float) -> None:
    result = trim_silence(noise(2.0, level))
    assert result.speech_s == 0.0
    assert len(result.samples) == 0


def test_digital_silence_has_no_speech() -> None:
    result = trim_silence(np.zeros(SAMPLE_RATE, dtype=np.float32))
    assert result.speech_s == 0.0
    assert len(result.samples) == 0


def test_a_click_shorter_than_three_frames_is_not_speech() -> None:
    audio = clip(noise(0.8, -65), noise(0.03, -15), noise(0.8, -65))
    assert trim_silence(audio).speech_s == 0.0


def test_a_short_word_is_speech() -> None:
    audio = clip(noise(0.8, -65), noise(0.12, -20), noise(0.8, -65))
    assert trim_silence(audio).speech_s == pytest.approx(0.12, abs=0.045)


def test_quiet_speech_over_a_very_quiet_floor_is_found() -> None:
    audio = clip(noise(0.5, -75), noise(1.0, -42), noise(0.5, -75))
    assert trim_silence(audio, pad_s=0.0).speech_s == pytest.approx(1.0, abs=0.06)


def test_a_steady_noise_floor_is_trimmed_off_the_speech() -> None:
    audio = clip(noise(0.7, -52), noise(1.0, -20), noise(0.7, -52))
    result = trim_silence(audio, pad_s=0.0)
    assert result.start_s == pytest.approx(0.7, abs=0.04)
    assert result.end_s == pytest.approx(1.7, abs=0.04)


def test_continuous_loud_audio_is_all_speech() -> None:
    result = trim_silence(noise(1.0, -20), pad_s=0.0)
    assert result.speech_s == pytest.approx(1.0, abs=0.04)


def test_input_shorter_than_one_frame_does_not_crash() -> None:
    result = trim_silence(np.ones(100, dtype=np.float32))
    assert result.speech_s == 0.0
    assert len(result.samples) == 0


def test_the_input_is_not_modified() -> None:
    audio = clip(noise(0.5, -65), noise(0.5, -20))
    before = audio.copy()
    trim_silence(audio)
    assert np.array_equal(audio, before)
