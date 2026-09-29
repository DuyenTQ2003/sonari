import numpy as np
import pytest
from ctc_align import token_spans, viterbi_align

BLANK = 0


def peaked(frame_tokens: list[int], vocab: int = 4, p: float = 0.9) -> np.ndarray:
    """Log posteriors with probability p on the given token at each frame."""
    probs = np.full((len(frame_tokens), vocab), (1 - p) / (vocab - 1))
    probs[np.arange(len(frame_tokens)), frame_tokens] = p
    return np.log(probs)


def test_aligns_tokens_to_their_peaks() -> None:
    log_probs = peaked([0, 1, 1, 0, 2, 0, 0, 3, 0])
    path = viterbi_align(log_probs, [1, 2, 3], BLANK)
    assert token_spans(path, 3) == [(1, 3), (4, 5), (7, 8)]


def test_repeated_token_needs_a_blank_between() -> None:
    log_probs = peaked([1, 1, 0, 1, 0])
    path = viterbi_align(log_probs, [1, 1], BLANK)
    first, second = token_spans(path, 2)
    assert first[1] <= 2 <= second[0]
    assert path[2] % 2 == 0  # the separating frame is a blank state


def test_forces_the_given_sequence_even_against_the_argmax() -> None:
    # The audio "says" token 2, but the reference is token 3: alignment must still place 3.
    log_probs = peaked([0, 2, 2, 0])
    path = viterbi_align(log_probs, [3], BLANK)
    assert len(token_spans(path, 1)) == 1


def test_too_few_frames_raises() -> None:
    with pytest.raises(ValueError):
        viterbi_align(peaked([1, 1]), [1, 1], BLANK)
