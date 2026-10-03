"""onnxruntime stand-ins for tests that do not need the real model."""

import threading

import numpy as np

from sonari_speech.runtime.model import expected_frames

VOCAB = 392


class FakeOrtSession:
    """Logits that depend on the input, so a test can tell what was fed."""

    def __init__(self) -> None:
        self.feeds: list[np.ndarray] = []

    def run(self, output_names: list[str], feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        assert output_names == ["logits"]
        values = feeds["input_values"]
        self.feeds.append(values)
        frames = expected_frames(values.shape[1])
        base = np.linspace(-3.0, 3.0, VOCAB, dtype=np.float32)
        logits = np.tile(base, (values.shape[0], frames, 1))
        return [logits + values.mean(axis=1)[:, None, None]]


class BlockingSession(FakeOrtSession):
    """Holds calls while `release` is clear; records how many ran at the same time.

    Starts open, so the warm-up passes; a test calls `close_gate()` after `start()`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self.release.set()
        self.entered = threading.Semaphore(0)
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def close_gate(self) -> None:
        """Block later calls and forget the warm-up call in the counters."""
        self.release.clear()
        self.entered = threading.Semaphore(0)
        self.peak = 0

    def run(self, output_names: list[str], feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        self.entered.release()
        assert self.release.wait(10), "test never released the session"
        with self._lock:
            self.active -= 1
        return super().run(output_names, feeds)
