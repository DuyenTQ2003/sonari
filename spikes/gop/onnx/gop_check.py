"""Rerun the P02 (gate G0) GOP numbers on ONNX log-posteriors and compare with torch.

    uv run --directory spikes/gop python onnx/gop_check.py --model fp32|int8

Same clips, same alignment, same GOP formula and same gate as run_gop.py; only the
source of the log-posteriors changes. Writes DATA_DIR/onnx/results/gop_<model>.json.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from audio_prep import log_softmax
from clips import data_dir, read_wav
from parity import onnx_logits, session

from run_gop import LEXICON, SUBSTITUTE, PhonemeScorer, Scorer


def gate(runs: dict) -> dict:
    ok, sub = runs["good-correct"][0], runs["good-substituted"][0]
    return {
        "theta_correct_gop": ok["gop"],
        "t_substituted_gop": sub["gop"],
        "competitor": sub["competitor"],
        "pass": ok["gop"] > 0 > sub["gop"] and sub["competitor"] == "θ",
    }


def score_all(log_probs_of, scorer: PhonemeScorer, manifest: dict) -> dict:
    runs = {}
    for clip_name in ("good", "bad"):
        clip = manifest[clip_name]
        log_probs = log_probs_of(read_wav(data_dir() / clip["file"]))
        correct = LEXICON[clip["word"]]
        substituted = [SUBSTITUTE[correct[0]], *correct[1:]]
        for ref_name, phones in (("correct", correct), ("substituted", substituted)):
            runs[f"{clip_name}-{ref_name}"] = scorer.score(log_probs, phones)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["fp32", "int8"], default="int8")
    name = parser.parse_args().model
    manifest = json.loads((data_dir() / "derived/g0/g0_manifest.json").read_text("utf-8"))
    torch_scorer = Scorer()
    reference = score_all(torch_scorer.log_probs, torch_scorer, manifest)
    sess = session(data_dir() / "onnx" / f"wav2vec2_{name}.onnx")

    scorer = PhonemeScorer(torch_scorer.blank)
    got = score_all(lambda a: log_softmax(onnx_logits(sess, a)), scorer, manifest)

    rows = []
    for run, segs in reference.items():
        for ref, new in zip(segs, got[run], strict=True):
            rows.append(
                {
                    "run": run,
                    "phone": ref["phone"],
                    "torch_ms": [ref["start_ms"], ref["end_ms"]],
                    f"{name}_ms": [new["start_ms"], new["end_ms"]],
                    "torch_gop": ref["gop"],
                    f"{name}_gop": new["gop"],
                    "delta_gop": round(new["gop"] - ref["gop"], 3),
                    "torch_competitor": ref["competitor"],
                    f"{name}_competitor": new["competitor"],
                }
            )
    result = {"rows": rows, "torch_gate": gate(reference), f"{name}_gate": gate(got)}
    out = data_dir() / "onnx" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"gop_{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    for r in rows:
        print(
            f"{r['run']:<18} {r['phone']:<3} torch {r['torch_ms']} gop {r['torch_gop']:>7.3f} "
            f"{r['torch_competitor']:<2} | {name} {r[f'{name}_ms']} gop {r[f'{name}_gop']:>7.3f} "
            f"{r[f'{name}_competitor']:<2} | delta {r['delta_gop']:+.3f}"
        )
    print("torch gate:", result["torch_gate"])
    print(f"{name} gate:", result[f"{name}_gate"])


if __name__ == "__main__":
    main()
