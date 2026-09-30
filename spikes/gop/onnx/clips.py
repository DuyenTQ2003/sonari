"""Fixed test audio for the ONNX scripts, all read from DATA_DIR (never the repo).

`g0_good`/`g0_bad`: the P01 word clips (about 0.8 s). `speech_3s`/`speech_8s`: the first 3.0
and 8.0 s of one fixed LibriSpeech dev-clean utterance (the shortest one of at least 8.5 s,
ties broken by id), so the timing clips are real read speech and identical on every run.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
from audio_prep import SAMPLE_RATE

MIN_SOURCE_S = 8.5


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


def read_wav(path: Path) -> np.ndarray:
    audio, sr = sf.read(path, dtype="float32")
    if sr != SAMPLE_RATE or audio.ndim != 1:
        raise ValueError(f"{path}: expected 16 kHz mono, got {sr} Hz {audio.shape}")
    return audio


def speech_clips() -> dict[str, np.ndarray]:
    index = pd.read_parquet(data_dir() / "librispeech" / "dev-clean.index.parquet")
    pick = (
        index[index["duration"] >= MIN_SOURCE_S].sort_values(["duration", "utterance_id"]).iloc[0]
    )
    audio = read_wav(data_dir() / pick["flac_path"])
    return {
        "speech_3s": audio[: 3 * SAMPLE_RATE],
        "speech_8s": audio[: 8 * SAMPLE_RATE],
    }


def g0_clips() -> dict[str, np.ndarray]:
    root = data_dir() / "derived" / "g0"
    return {"g0_good": read_wav(root / "good.wav"), "g0_bad": read_wav(root / "bad.wav")}


def all_clips() -> dict[str, np.ndarray]:
    return {**g0_clips(), **speech_clips()}
