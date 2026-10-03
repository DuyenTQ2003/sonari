"""Energy-based trim of leading and trailing silence.

No model, no dependencies beyond numpy. Levels are relative to the clip (its own noise
floor and loudest frames), so a quiet recording and a noisy room both work; two absolute
limits stop silence and steady noise from being called speech.
"""

from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16000
FRAME = SAMPLE_RATE // 50  # 20 ms, the model's own frame
MIN_RUN = 3  # consecutive loud frames that make speech: a click is not a word
INAUDIBLE_DB = -55.0  # a clip whose loudest frames are quieter than this has no speech
CONTINUOUS_DB = -40.0  # with no quiet part at all, speech means at least this loud
MIN_RANGE_DB = 12.0  # loudest minus floor below this: no pauses to tell speech from noise
THRESHOLD_STEP_DB = 10.0  # speech is at least this far above the floor ...
THRESHOLD_FRACTION = 0.35  # ... or this fraction of the clip's range, whichever is more
EPS = 1e-10


@dataclass(frozen=True, slots=True)
class Trimmed:
    """The padded speech part of a clip and where the speech itself lies in the original."""

    samples: np.ndarray
    start_s: float  # first speech frame, in the original clip
    end_s: float  # end of the last speech frame
    speech_s: float  # end_s - start_s; pauses inside the speech count


def _empty() -> Trimmed:
    return Trimmed(np.zeros(0, dtype=np.float32), 0.0, 0.0, 0.0)


def _frame_db(samples: np.ndarray) -> np.ndarray:
    frames = samples[: len(samples) // FRAME * FRAME].reshape(-1, FRAME).astype(np.float64)
    return np.asarray(20.0 * np.log10(np.sqrt((frames**2).mean(axis=1)) + EPS))


def _active_frames(db: np.ndarray) -> np.ndarray:
    floor, peak = np.percentile(db, 10), np.percentile(db, 99)
    if peak < INAUDIBLE_DB:
        return np.zeros(len(db), dtype=bool)
    if peak - floor < MIN_RANGE_DB:
        return np.full(len(db), peak >= CONTINUOUS_DB)
    threshold = floor + max(THRESHOLD_STEP_DB, THRESHOLD_FRACTION * (peak - floor))
    return np.asarray(db > threshold)


def _runs(active: np.ndarray) -> np.ndarray:
    """True where a frame starts a run of MIN_RUN loud frames."""
    windows = np.lib.stride_tricks.sliding_window_view(active, MIN_RUN)
    return np.asarray(windows.all(axis=1))


def trim_silence(
    samples: np.ndarray, sample_rate: int = SAMPLE_RATE, pad_s: float = 0.15
) -> Trimmed:
    """Cut the silence before and after the speech, keeping `pad_s` of it on each side.

    `samples` is mono float32 at 16 kHz. Returns an empty `Trimmed` when there is no speech.
    """
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"expected {SAMPLE_RATE} Hz audio, got {sample_rate}")
    if len(samples) < FRAME * MIN_RUN:
        return _empty()
    starts = np.flatnonzero(_runs(_active_frames(_frame_db(samples))))
    if len(starts) == 0:
        return _empty()
    first, last = int(starts[0]), int(starts[-1]) + MIN_RUN  # last is one past the final frame
    pad = int(pad_s * SAMPLE_RATE)
    begin, end = max(0, first * FRAME - pad), min(len(samples), last * FRAME + pad)
    return Trimmed(
        samples[begin:end].copy(),
        first * FRAME / SAMPLE_RATE,
        last * FRAME / SAMPLE_RATE,
        (last - first) * FRAME / SAMPLE_RATE,
    )
