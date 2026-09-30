"""numpy-only helpers shared by the ONNX scripts and their tests.

The production image runs onnxruntime + numpy only, so preprocessing and post-processing
are reimplemented here instead of using transformers.
"""

import numpy as np

SAMPLE_RATE = 16000
FRAME_S = 320 / SAMPLE_RATE  # wav2vec2 emits one frame per 320 samples (20 ms)
NORM_EPS = 1e-7  # transformers' Wav2Vec2FeatureExtractor zero_mean_unit_var_norm


def normalise(audio: np.ndarray) -> np.ndarray:
    """Zero mean, unit variance per utterance, as the model's feature extractor does."""
    audio = audio.astype(np.float32, copy=False)
    return ((audio - audio.mean()) / np.sqrt(audio.var() + NORM_EPS)).astype(np.float32)


def log_softmax(logits: np.ndarray) -> np.ndarray:
    """Log posteriors over the last axis, computed in float64 for a stable difference."""
    x = logits.astype(np.float64)
    x = x - x.max(axis=-1, keepdims=True)
    return (x - np.log(np.exp(x).sum(axis=-1, keepdims=True))).astype(np.float32)


def greedy_ids(log_probs: np.ndarray, blank: int) -> list[int]:
    """Greedy CTC decode of one utterance: collapse repeats, drop blanks."""
    best = log_probs.argmax(axis=-1)
    out, prev = [], -1
    for tok in best.tolist():
        if tok != prev and tok != blank:
            out.append(tok)
        prev = tok
    return out


def expected_frames(n_samples: int) -> int:
    """Frames the wav2vec2 conv stack produces for n_samples (kernel 400, stride 320)."""
    length = n_samples
    for kernel, stride in [(10, 5), (3, 2), (3, 2), (3, 2), (3, 2), (2, 2), (2, 2)]:
        length = (length - kernel) // stride + 1
    return length
