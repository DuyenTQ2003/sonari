"""Numerical parity between the torch model and an ONNX file.

    uv run --directory spikes/gop python onnx/parity.py [--model fp32|int8]

For each test clip: max and mean absolute difference of the log-posteriors (log-softmax
of the logits, float64 inside), the frame counts, and whether the greedy CTC decode is
identical. Results go to DATA_DIR/onnx/results/parity_<model>.json for BENCH.md.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from transformers import Wav2Vec2ForCTC

sys.path.append(str(Path(__file__).resolve().parents[1]))
from audio_prep import expected_frames, greedy_ids, log_softmax, normalise
from clips import all_clips, data_dir
from export import MODEL


def session(path: Path, threads: int = 4) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])


def onnx_logits(sess: ort.InferenceSession, audio: np.ndarray) -> np.ndarray:
    return sess.run(["logits"], {"input_values": normalise(audio)[None]})[0][0]


def torch_logits(model: Wav2Vec2ForCTC, audio: np.ndarray) -> np.ndarray:
    with torch.inference_mode():
        return model(torch.from_numpy(normalise(audio))[None]).logits[0].numpy()


def compare(model: Wav2Vec2ForCTC, sess: ort.InferenceSession, blank: int) -> dict[str, dict]:
    rows = {}
    for name, audio in all_clips().items():
        ref, got = torch_logits(model, audio), onnx_logits(sess, audio)
        assert ref.shape == got.shape == (expected_frames(len(audio)), ref.shape[1]), name
        lp_ref, lp_got = log_softmax(ref), log_softmax(got)
        rows[name] = {
            "seconds": round(len(audio) / 16000, 2),
            "frames": int(ref.shape[0]),
            "max_abs_logprob_diff": float(np.abs(lp_ref - lp_got).max()),
            "mean_abs_logprob_diff": float(np.abs(lp_ref - lp_got).mean()),
            "max_abs_logit_diff": float(np.abs(ref - got).max()),
            "argmax_frames_equal": float((lp_ref.argmax(-1) == lp_got.argmax(-1)).mean()),
            "decode_identical": greedy_ids(lp_ref, blank) == greedy_ids(lp_got, blank),
        }
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["fp32", "int8"], default="fp32")
    name = parser.parse_args().model
    model = Wav2Vec2ForCTC.from_pretrained(MODEL, attn_implementation="eager").eval()
    sess = session(data_dir() / "onnx" / f"wav2vec2_{name}.onnx")
    rows = compare(model, sess, model.config.pad_token_id)
    out = data_dir() / "onnx" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"parity_{name}.json").write_text(json.dumps(rows, indent=2), "utf-8")
    for clip, r in rows.items():
        print(
            f"{name} {clip:<10} {r['seconds']:>5}s {r['frames']:>4} frames  "
            f"max|dlogp|={r['max_abs_logprob_diff']:.2e}  mean={r['mean_abs_logprob_diff']:.2e}  "
            f"decode identical={r['decode_identical']}"
        )


if __name__ == "__main__":
    main()
