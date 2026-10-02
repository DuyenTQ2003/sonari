import stat
import wave
from pathlib import Path

import numpy as np
import pytest
from tests.support import needs_ffmpeg

from sonari_speech.errors import AppError, MessageKey
from sonari_speech.runtime.audio import (
    SAMPLE_RATE,
    DecoderUnavailable,
    decode_audio,
    ffmpeg_available,
    sniff_demuxer,
)
from sonari_speech.settings import Settings

FIXTURES = Path(__file__).parents[1] / "fixtures"
FIXTURE_SECONDS = 2.0  # tests/fixtures/generate.py

pytestmark = needs_ffmpeg


def wav_bytes(samples: np.ndarray, rate: int, channels: int, tmp_path: Path) -> bytes:
    path = tmp_path / "in.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((samples * 32767).astype("<i2").tobytes())
    return path.read_bytes()


def tone(seconds: float, rate: int, hz: float = 220.0, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


async def decode(data: bytes, **overrides: object) -> np.ndarray:
    return await decode_audio(data, Settings(**overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["chrome.webm", "firefox.ogg", "ios.m4a", "ios-fragmented.mp4"])
async def test_browser_recordings_decode_to_16k_mono_float32_of_the_right_length(name: str) -> None:
    audio = await decode((FIXTURES / name).read_bytes())
    assert audio.dtype == np.float32
    assert audio.ndim == 1
    assert np.isfinite(audio).all()
    # 2 %: AAC adds up to one 21 ms priming frame, and the silent edges are trimmed later.
    assert len(audio) / SAMPLE_RATE == pytest.approx(FIXTURE_SECONDS, rel=0.02)
    assert np.abs(audio).max() > 0.05  # the tone survived


async def test_an_ios_m4a_and_a_chrome_webm_decode_to_the_same_length_within_one_percent() -> None:
    m4a = await decode((FIXTURES / "ios.m4a").read_bytes())
    webm = await decode((FIXTURES / "chrome.webm").read_bytes())
    assert abs(len(m4a) - len(webm)) / len(webm) < 0.01


async def test_a_44k_stereo_wav_is_resampled_and_downmixed(tmp_path: Path) -> None:
    left, right = tone(1.0, 44100, 220), tone(1.0, 44100, 220)
    audio = await decode(wav_bytes(np.stack([left, right], axis=1), 44100, 2, tmp_path))
    assert len(audio) == pytest.approx(SAMPLE_RATE, abs=64)
    spectrum = np.abs(np.fft.rfft(audio))
    assert np.argmax(spectrum) * SAMPLE_RATE / len(audio) == pytest.approx(220, abs=2)
    # ffmpeg sums the channels with equal power (+3 dB for identical ones); the model
    # normalises the level anyway, so only "not silent, not wild" is asserted.
    assert 0.5 < float(np.sqrt((audio**2).mean())) / (0.3 / np.sqrt(2)) < 2.0


async def test_a_16k_mono_wav_passes_through_unchanged_in_length(tmp_path: Path) -> None:
    audio = await decode(wav_bytes(tone(0.8, 16000), 16000, 1, tmp_path))
    assert len(audio) == int(0.8 * 16000)


@pytest.mark.parametrize("data", [b"", b"not audio at all", b"RIFF\x00\x00\x00\x00WAVEjunk" * 4])
async def test_bytes_that_are_not_audio_are_rejected_as_undecodable(data: bytes) -> None:
    with pytest.raises(AppError) as err:
        await decode(data)
    assert err.value.message_key is MessageKey.AUDIO_UNDECODABLE
    assert err.value.status_code == 415


async def test_a_playlist_is_not_followed_to_the_network_or_the_disk() -> None:
    hostile = b"#EXTM3U\n#EXTINF:1,\nhttp://127.0.0.1:9/x.mp3\nfile:///etc/passwd\n"
    with pytest.raises(AppError) as err:
        await decode(hostile)
    assert err.value.message_key is MessageKey.AUDIO_UNDECODABLE


async def test_a_clip_over_the_size_limit_is_rejected_before_decoding(tmp_path: Path) -> None:
    data = wav_bytes(tone(1.0, 16000), 16000, 1, tmp_path)
    with pytest.raises(AppError) as err:
        await decode(data, max_upload_bytes=1000)
    assert err.value.message_key is MessageKey.AUDIO_TOO_LARGE
    assert err.value.status_code == 413


async def test_a_clip_longer_than_the_limit_is_rejected(tmp_path: Path) -> None:
    data = wav_bytes(tone(20.0, 16000), 16000, 1, tmp_path)
    with pytest.raises(AppError) as err:
        await decode(data)
    assert err.value.message_key is MessageKey.AUDIO_TOO_LONG
    assert err.value.status_code == 422


async def test_a_clip_of_exactly_the_limit_is_accepted(tmp_path: Path) -> None:
    audio = await decode(wav_bytes(tone(15.0, 16000), 16000, 1, tmp_path))
    assert len(audio) == 15 * SAMPLE_RATE


async def test_a_very_long_clip_is_not_decoded_to_the_end(tmp_path: Path) -> None:
    data = wav_bytes(tone(120.0, 16000), 16000, 1, tmp_path)
    with pytest.raises(AppError) as err:
        await decode(data, max_upload_bytes=10_000_000)
    assert err.value.message_key is MessageKey.AUDIO_TOO_LONG


async def test_a_decoder_that_hangs_is_killed_and_the_clip_rejected(tmp_path: Path) -> None:
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\nsleep 30\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    data = wav_bytes(tone(0.5, 16000), 16000, 1, tmp_path)
    with pytest.raises(AppError) as err:
        await decode(data, ffmpeg_path=str(fake), decode_timeout_s=0.3)
    assert err.value.message_key is MessageKey.AUDIO_UNDECODABLE


async def test_a_missing_ffmpeg_is_a_server_error_not_a_bad_upload(tmp_path: Path) -> None:
    data = wav_bytes(tone(0.5, 16000), 16000, 1, tmp_path)
    with pytest.raises(DecoderUnavailable):
        await decode(data, ffmpeg_path="/nonexistent/ffmpeg")


def test_ffmpeg_available_reports_the_binary_by_path_or_name() -> None:
    assert ffmpeg_available(Settings()) is True
    assert ffmpeg_available(Settings(ffmpeg_path="/nonexistent/ffmpeg")) is False


@pytest.mark.parametrize(
    ("name", "demuxer"),
    [
        ("chrome.webm", "matroska,webm"),
        ("firefox.ogg", "ogg"),
        ("ios.m4a", "mov,mp4,m4a,3gp,3g2,mj2"),
        ("ios-fragmented.mp4", "mov,mp4,m4a,3gp,3g2,mj2"),
    ],
)
def test_the_container_is_recognised_from_its_first_bytes(name: str, demuxer: str) -> None:
    assert sniff_demuxer((FIXTURES / name).read_bytes()) == demuxer


def test_wav_is_recognised_and_other_data_is_not(tmp_path: Path) -> None:
    assert sniff_demuxer(wav_bytes(tone(0.1, 16000), 16000, 1, tmp_path)) == "wav"
    assert sniff_demuxer(b"#EXTM3U\n") is None
    assert sniff_demuxer(b"") is None
