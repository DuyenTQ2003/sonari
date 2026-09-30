"""Assemble BENCH.md from the JSON files the other scripts wrote.

    uv run --directory spikes/gop python onnx/report.py

Every number in the tables comes from DATA_DIR/onnx/results/*.json; the prose is fixed
text, and the verdict lines are computed from the data.
"""

import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from clips import data_dir

HERE = Path(__file__).parent
MODELS = ("fp32", "int8")
THREADS = (1, 2, 4)
CLIPS = ("speech_3s", "speech_8s")


def load(name: str) -> dict:
    return json.loads((data_dir() / "onnx" / "results" / name).read_text("utf-8"))


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def lscpu(field: str) -> str:
    out = subprocess.run(["lscpu"], capture_output=True, text=True, check=True).stdout
    return next(
        (line.split(":", 1)[1].strip() for line in out.splitlines() if line.startswith(field)), "?"
    )


def latency_table() -> str:
    rows = []
    for clip in CLIPS:
        for model in MODELS:
            cells = []
            for t in THREADS:
                r = load(f"bench_{model}_t{t}_{clip}.json")
                cells.append(f"{r['p50_ms']:.0f} / {r['p95_ms']:.0f} ({r['rtf_p50']:.2f})")
            seconds = load(f"bench_{model}_t1_{clip}.json")["clip_seconds"]
            rows.append([f"{seconds:g} s", model, *cells])
    return table(["Clip", "Model", "1 thread", "2 threads", "4 threads"], rows)


def memory_table() -> str:
    rows = []
    for model in MODELS:
        runs = [load(f"bench_{model}_t{t}_{c}.json") for t in THREADS for c in CLIPS]
        rows.append(
            [
                model,
                f"{runs[0]['model_file_mb']}",
                f"{min(r['peak_rss_mb'] for r in runs)}-{max(r['peak_rss_mb'] for r in runs)}",
                f"{min(r['session_load_s'] for r in runs):.1f}-"
                f"{max(r['session_load_s'] for r in runs):.1f}",
            ]
        )
    return table(["Model", "File (MB)", "Peak RSS (MB, all configs)", "Session load (s)"], rows)


def parity_table() -> str:
    rows = []
    for model in MODELS:
        for clip, r in load(f"parity_{model}.json").items():
            rows.append(
                [
                    model,
                    f"{clip} ({r['seconds']:g} s)",
                    f"{r['max_abs_logprob_diff']:.1e}",
                    f"{r['mean_abs_logprob_diff']:.1e}",
                    f"{r['argmax_frames_equal']:.1%}",
                    "yes" if r["decode_identical"] else "**NO**",
                ]
            )
    return table(
        [
            "Model",
            "Clip",
            "Max abs diff (nats)",
            "Mean abs diff",
            "Same argmax frames",
            "Same decode",
        ],
        rows,
    )


def gop_table() -> tuple[str, dict, dict]:
    fp32, int8 = load("gop_fp32.json"), load("gop_int8.json")
    rows = []
    for a, b in zip(fp32["rows"], int8["rows"], strict=True):
        same_span = a["fp32_ms"] == b["int8_ms"] == b["torch_ms"]
        rows.append(
            [
                a["run"],
                a["phone"],
                f"{a['torch_gop']:+.3f}",
                f"{a['fp32_gop']:+.3f}",
                f"{b['int8_gop']:+.3f}",
                f"{b['delta_gop']:+.3f}",
                f"{b['torch_competitor']} / {b['int8_competitor']}",
                "same" if same_span else "**moved**",
            ]
        )
    header = [
        "Run",
        "Phone",
        "torch",
        "ONNX fp32",
        "ONNX int8",
        "int8 - torch",
        "Competitor (torch / int8)",
        "Span",
    ]
    return table(header, rows), fp32["torch_gate"], int8["int8_gate"]


def capacity_table() -> str:
    rows = []
    for model in MODELS:
        cells = []
        for c in THREADS:
            r = load(f"concurrency_{model}_c{c}.json")
            cells.append(
                f"{r['max_concurrent_within_budget']} (1 req: {r['single_request_p50_ms']} ms)"
            )
        rows.append([model, *cells])
    return table(["Model", "1 core", "2 cores", "4 cores"], rows)


def gate_text(gate: dict) -> str:
    return (
        f"gop(θ | correct) = {gate['theta_correct_gop']:+.3f}, "
        f"gop(t | substituted) = {gate['t_substituted_gop']:+.3f}, "
        f"competitor {gate['competitor']}"
    )


def main() -> None:
    gop_rows, torch_gate, int8_gate = gop_table()
    gate_changed = torch_gate["pass"] != int8_gate["pass"]
    max_delta = max(abs(r["delta_gop"]) for r in load("gop_int8.json")["rows"])
    env = {
        "cpu": lscpu("Model name"),
        "threads": lscpu("CPU(s)"),
        "ram": subprocess.run(["free", "-m"], capture_output=True, text=True)
        .stdout.split("\n")[1]
        .split()[1],
    }
    text = (
        (HERE / "BENCH.template.md")
        .read_text("utf-8")
        .format(
            cpu=env["cpu"],
            logical=env["threads"],
            ram_mb=env["ram"],
            platform=platform.platform(),
            torch=version("torch"),
            onnx=version("onnx"),
            ort=version("onnxruntime"),
            opset=20,
            latency=latency_table(),
            memory=memory_table(),
            parity=parity_table(),
            gop=gop_rows,
            torch_gate=gate_text(torch_gate),
            int8_gate=gate_text(int8_gate),
            max_delta=f"{max_delta:.3f}",
            gate_verdict="CHANGES" if gate_changed else "does not change",
            torch_pass="PASS" if torch_gate["pass"] else "FAIL",
            int8_pass="PASS" if int8_gate["pass"] else "FAIL",
            capacity=capacity_table(),
        )
    )
    (HERE / "BENCH.md").write_text(text, "utf-8")
    print(f"wrote {HERE / 'BENCH.md'}")


if __name__ == "__main__":
    main()
