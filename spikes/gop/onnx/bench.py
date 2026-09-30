"""CPU latency of one ONNX model on one clip length and one intra-op thread count.

    uv run --directory spikes/gop python onnx/bench.py --model fp32 --threads 2 --clip speech_3s

One process per configuration, so peak RSS is that configuration's own. The process is
pinned to one hardware thread per physical core (as many as --threads) to make runs
repeatable and to mimic a VPS with that many dedicated cores. Timed per request:
normalise + session.run + log-softmax (the numpy pipeline of the production image).
Alignment and GOP are not timed here. Writes DATA_DIR/onnx/results/bench_<model>_t<T>_<clip>.json.
"""

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

sys.path.append(str(Path(__file__).resolve().parents[1]))
from audio_prep import log_softmax, normalise
from bench_stats import summarise
from clips import all_clips, data_dir


def physical_cpus() -> list[int]:
    """One hardware thread per physical core, lowest CPU number first."""
    seen: set[str] = set()
    cpus = []
    for cpu in sorted(os.sched_getaffinity(0)):
        siblings = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list")
        key = siblings.read_text().strip() if siblings.exists() else str(cpu)
        if key not in seen:
            seen.add(key)
            cpus.append(cpu)
    return cpus


def rss_mb() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return float("nan")


def make_session(path: Path, threads: int) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])


def request(sess: ort.InferenceSession, audio: np.ndarray) -> np.ndarray:
    logits = sess.run(["logits"], {"input_values": normalise(audio)[None]})[0][0]
    return log_softmax(logits)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["fp32", "int8"], required=True)
    parser.add_argument("--threads", type=int, required=True)
    parser.add_argument("--clip", choices=["speech_3s", "speech_8s"], required=True)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()

    cpus = physical_cpus()[: args.threads]
    if len(cpus) < args.threads:
        sys.exit(f"only {len(cpus)} physical cores available")
    os.sched_setaffinity(0, cpus)
    load_start = os.getloadavg()[0]

    path = data_dir() / "onnx" / f"wav2vec2_{args.model}.onnx"
    audio = all_clips()[args.clip]
    t0 = time.perf_counter()
    sess = make_session(path, args.threads)
    load_s = time.perf_counter() - t0
    for _ in range(args.warmup):
        request(sess, audio)
    samples = []
    for _ in range(args.runs):
        t = time.perf_counter()
        request(sess, audio)
        samples.append((time.perf_counter() - t) * 1000)

    stats = summarise(samples)
    result = {
        "model": args.model,
        "threads": args.threads,
        "clip": args.clip,
        "clip_seconds": round(len(audio) / 16000, 2),
        "cpus": cpus,
        "warmup": args.warmup,
        **stats,
        "rtf_p50": round(stats["p50_ms"] / 1000 / (len(audio) / 16000), 3),
        "session_load_s": round(load_s, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        "steady_rss_mb": round(rss_mb()),
        "model_file_mb": round(path.stat().st_size / 1e6),
        "loadavg_start": round(load_start, 2),
        "loadavg_end": round(os.getloadavg()[0], 2),
        "samples_ms": [round(s, 1) for s in samples],
    }
    out = data_dir() / "onnx" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"bench_{args.model}_t{args.threads}_{args.clip}.json").write_text(
        json.dumps(result), "utf-8"
    )
    print({k: v for k, v in result.items() if k not in ("samples_ms", "cpus")}, "cpus", cpus)


if __name__ == "__main__":
    main()
