"""Regenerate the audio fixtures: `python tests/fixtures/generate.py` (needs ffmpeg).

These are SYNTHETIC: a 2.0 s speech-like signal (0.4 s of low noise, 1.2 s of a harmonic
tone with a 4 Hz syllable envelope, 0.4 s of low noise), encoded the way each browser
encodes a recording. They are not recordings from a real device; replace them with real
ones when you have them (the decode test only needs 2.0 s files).

    chrome.webm          Chrome MediaRecorder: WebM, Opus, 48 kHz mono
    firefox.ogg          Firefox MediaRecorder: Ogg, Opus, 48 kHz mono
    ios.m4a              iPhone upload: MP4 with AAC-LC, 48 kHz mono, moov atom at the END
    ios-fragmented.mp4   Safari MediaRecorder: fragmented MP4, AAC-LC, 48 kHz mono
"""

import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent


def signal(rate: int) -> np.ndarray:
    """The test signal at its own sample rate, so that ffmpeg never resamples it (a resample
    adds a few milliseconds of its own and would blur the length comparison)."""
    rng = np.random.default_rng(1)
    t = np.arange(int(1.2 * rate)) / rate
    voiced = sum(np.sin(2 * np.pi * 140 * k * t) / k for k in range(1, 12))
    envelope = 0.5 * (1 - np.cos(2 * np.pi * 4 * t))
    tone = 0.25 * envelope * voiced / 3
    floor = lambda s: rng.normal(0, 0.0005, int(s * rate))  # noqa: E731
    return np.concatenate([floor(0.4), tone, floor(0.4)]).astype(np.float32)


def write_wav(path: Path, rate: int) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((signal(rate) * 32767).astype("<i2").tobytes())


def main() -> None:
    jobs = {  # name: (sample rate, ffmpeg output arguments)
        "chrome.webm": (48000, ["-c:a", "libopus", "-b:a", "24k"]),
        "firefox.ogg": (48000, ["-c:a", "libopus", "-b:a", "24k"]),
        "ios.m4a": (48000, ["-c:a", "aac", "-b:a", "48k", "-f", "ipod"]),
        "ios-fragmented.mp4": (
            48000,
            ["-c:a", "aac", "-b:a", "48k", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4"],
        ),
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, (rate, args) in jobs.items():
            source = Path(tmp) / f"{rate}.wav"
            write_wav(source, rate)
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", source, "-ac", "1", *args, HERE / name]
            subprocess.run([str(c) for c in cmd], check=True)
            print(name, (HERE / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
