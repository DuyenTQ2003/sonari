"""The wav2vec2 phoneme model on onnxruntime, numpy in and numpy out (no torch).

Pre- and post-processing are the numpy versions from spikes/gop/onnx/audio_prep.py (P04),
which reproduced torch to 1.2e-4 nats on fp32. The deployed file is the int8 one; G1's
thresholds are calibrated on it (BENCH.md, "Condition on using int8").
"""

import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from opentelemetry import trace

SAMPLE_RATE = 16000
FRAME_S = 320 / SAMPLE_RATE  # wav2vec2 emits one frame per 320 samples (20 ms)
MIN_SAMPLES = 400  # receptive field of one frame
NORM_EPS = 1e-7  # transformers' Wav2Vec2FeatureExtractor zero_mean_unit_var_norm
WARMUP_SECONDS = 1.0
_CONV_STACK = [(10, 5), (3, 2), (3, 2), (3, 2), (3, 2), (2, 2), (2, 2)]  # (kernel, stride)

tracer = trace.get_tracer("sonari_speech")


def normalise(audio: np.ndarray) -> np.ndarray:
    """Zero mean, unit variance per utterance, as the model's feature extractor does."""
    audio = audio.astype(np.float32, copy=False)
    out: np.ndarray = (audio - audio.mean()) / np.sqrt(audio.var() + NORM_EPS)
    return out.astype(np.float32)


def log_softmax(logits: np.ndarray) -> np.ndarray:
    """Log posteriors over the last axis, computed in float64 for a stable difference."""
    x = logits.astype(np.float64)
    x = x - x.max(axis=-1, keepdims=True)
    out: np.ndarray = x - np.log(np.exp(x).sum(axis=-1, keepdims=True))
    return out.astype(np.float32)


def expected_frames(n_samples: int) -> int:
    """Frames the conv stack produces for `n_samples` of audio."""
    length = n_samples
    for kernel, stride in _CONV_STACK:
        length = (length - kernel) // stride + 1
    return length


class ModelSession:
    """One onnxruntime session, shared by every request; `infer` is safe to call concurrently."""

    def __init__(self, session: Any) -> None:
        self._session = session

    @classmethod
    def load(cls, path: Path, intra_op_threads: int) -> "ModelSession":
        if not path.is_file():
            raise FileNotFoundError(f"model file not found: {path}")
        options = ort.SessionOptions()
        options.intra_op_num_threads = intra_op_threads
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        return cls(session)

    @classmethod
    def from_session(cls, session: Any) -> "ModelSession":
        """Wrap anything with onnxruntime's `run`; tests pass a fake."""
        return cls(session)

    def infer(self, audio: np.ndarray) -> np.ndarray:
        """Log-posteriors, float32 [frames, vocab], for mono 16 kHz audio (blocking)."""
        if len(audio) < MIN_SAMPLES:
            raise ValueError(f"need at least {MIN_SAMPLES} samples, got {len(audio)}")
        with tracer.start_as_current_span("speech.infer") as span:
            span.set_attribute("audio.seconds", len(audio) / SAMPLE_RATE)
            logits = self._session.run(["logits"], {"input_values": normalise(audio)[None]})[0][0]
            span.set_attribute("model.frames", int(logits.shape[0]))
            return log_softmax(logits)

    def warmup(self) -> float:
        """One inference on a second of noise, so the first request does not pay for it."""
        noise = np.random.default_rng(0).normal(0, 0.1, int(WARMUP_SECONDS * SAMPLE_RATE))
        start = time.perf_counter()
        self.infer(noise.astype(np.float32))
        return time.perf_counter() - start
