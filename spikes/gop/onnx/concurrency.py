"""How many simultaneous scoring requests fit under a p95 latency budget.

    uv run --directory spikes/gop python onnx/concurrency.py --model int8 --cores 2

Emulates a VPS with `--cores` dedicated cores (the process is pinned to that many
physical cores). One shared onnxruntime session with a single intra-op thread, N Python
threads that all start at once (a burst), latency measured from the start of the burst
to the end of each request, queueing included. Bursts repeat; p95 is over every request.
N grows until p95 exceeds the budget. Writes results/concurrency_<model>_c<C>.json.
"""

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from bench import make_session, physical_cpus, request
from bench_stats import burst_capacity, percentile
from clips import all_clips, data_dir

BUDGET_MS = 2000.0
MAX_N = 24


def burst(sess, audio, n: int) -> list[float]:
    """Latency (ms) of n requests started together."""
    barrier = threading.Barrier(n + 1)
    latencies: list[float] = [0.0] * n

    def worker(i: int) -> None:
        barrier.wait()
        request(sess, audio)
        latencies[i] = (time.perf_counter() - start) * 1000

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    start = time.perf_counter()
    barrier.wait()
    for t in threads:
        t.join()
    return latencies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["fp32", "int8"], required=True)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--clip", default="speech_3s", choices=["speech_3s", "speech_8s"])
    parser.add_argument("--bursts", type=int, default=6)
    args = parser.parse_args()

    cpus = physical_cpus()[: args.cores]
    os.sched_setaffinity(0, cpus)
    audio = all_clips()[args.clip]
    sess = make_session(data_dir() / "onnx" / f"wav2vec2_{args.model}.onnx", threads=1)
    for _ in range(3):
        request(sess, audio)
    single = [burst(sess, audio, 1)[0] for _ in range(10)]
    service_ms = percentile(single, 50)

    table, best, failures = [], 0, 0
    for n in range(1, MAX_N + 1):
        lat = [x for _ in range(args.bursts) for x in burst(sess, audio, n)]
        p95, p50 = percentile(lat, 95), percentile(lat, 50)
        ok = p95 <= BUDGET_MS
        table.append({"n": n, "p50_ms": round(p50), "p95_ms": round(p95), "within_budget": ok})
        print(
            f"{args.model} cores={args.cores} N={n:>2}  p50={p50:>6.0f} ms  "
            f"p95={p95:>6.0f} ms  {'ok' if ok else 'OVER'}"
        )
        best = n if ok else best
        failures = 0 if ok else failures + 1
        if failures >= 2:
            break
    result = {
        "model": args.model,
        "cores": args.cores,
        "cpus": cpus,
        "clip": args.clip,
        "budget_ms": BUDGET_MS,
        "single_request_p50_ms": round(service_ms),
        "max_concurrent_within_budget": best,
        "arithmetic_estimate": burst_capacity(service_ms, args.cores, BUDGET_MS),
        "table": table,
    }
    out = data_dir() / "onnx" / "results"
    (out / f"concurrency_{args.model}_c{args.cores}.json").write_text(json.dumps(result), "utf-8")
    print(
        f"max concurrent under {BUDGET_MS:.0f} ms p95: {best} "
        f"(single-request p50 {service_ms:.0f} ms; "
        f"arithmetic estimate {result['arithmetic_estimate']})"
    )


if __name__ == "__main__":
    main()
