"""CTC Viterbi forced alignment in numpy (no torchaudio: production runs onnxruntime + numpy).

Ported from spikes/gop/align.py (P02), itself a copy of tools/evaldata/ctc_align.py; the
only change is the TooFewFrames error, a ValueError as before. The service aligns the whole
reference sentence, not one word, so every phoneme is pinned between its neighbours and an
absent phoneme cannot drift into a context word (the P02 finding on bad.wav).
"""

import numpy as np


class TooFewFrames(ValueError):
    """The recording is too short to hold every token of the reference."""


def viterbi_align(log_probs: np.ndarray, targets: list[int], blank: int = 0) -> np.ndarray:
    """Return the best CTC state path, one extended-state index per frame.

    log_probs: (T, V) log posteriors. The extended sequence is blank, t0, blank, t1, ...,
    blank; state s = 2k + 1 is target token k, even states are blanks. Raises TooFewFrames
    when the frames cannot hold the targets.
    """
    n_frames = log_probs.shape[0]
    ext = np.full(2 * len(targets) + 1, blank, dtype=np.int64)
    ext[1::2] = targets
    n_states = len(ext)
    # A skip from s-2 to s is allowed only into a non-blank that differs from ext[s-2].
    can_skip = np.zeros(n_states, dtype=bool)
    can_skip[2:] = (ext[2:] != blank) & (ext[2:] != ext[:-2])
    repeats = int(np.sum(np.asarray(targets[1:]) == np.asarray(targets[:-1])))
    if n_frames < len(targets) + repeats:
        raise TooFewFrames(f"{n_frames} frames cannot hold {len(targets)} tokens")

    score = np.full(n_states, -np.inf)
    score[0] = log_probs[0, ext[0]]
    if n_states > 1:
        score[1] = log_probs[0, ext[1]]
    back = np.zeros((n_frames, n_states), dtype=np.int8)  # 0 stay, 1 from s-1, 2 from s-2
    for t in range(1, n_frames):
        stay = score
        step = np.concatenate(([-np.inf], score[:-1]))
        skip = np.where(can_skip, np.concatenate(([-np.inf, -np.inf], score[:-2])), -np.inf)
        choices = np.stack([stay, step, skip])
        back[t] = np.argmax(choices, axis=0)
        score = choices.max(axis=0) + log_probs[t, ext]

    final = n_states - 1 if n_states == 1 or score[-1] >= score[-2] else n_states - 2
    path = np.empty(n_frames, dtype=np.int64)
    path[-1] = final
    for t in range(n_frames - 1, 0, -1):
        path[t - 1] = path[t] - back[t, path[t]]
    return path


def token_spans(path: np.ndarray, n_targets: int) -> list[tuple[int, int]]:
    """Frame span [start, end) of each target token along a state path."""
    spans = []
    for k in range(n_targets):
        frames = np.flatnonzero(path == 2 * k + 1)
        spans.append((int(frames[0]), int(frames[-1]) + 1))
    return spans
