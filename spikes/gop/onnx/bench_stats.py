"""Latency statistics and capacity arithmetic for the benchmark. numpy only."""

import numpy as np


def percentile(samples_ms: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(samples_ms, dtype=np.float64), q))


def summarise(samples_ms: list[float]) -> dict[str, float]:
    return {
        "n": len(samples_ms),
        "p50_ms": round(percentile(samples_ms, 50), 1),
        "p95_ms": round(percentile(samples_ms, 95), 1),
        "min_ms": round(min(samples_ms), 1),
        "max_ms": round(max(samples_ms), 1),
    }


def burst_capacity(service_ms: float, cores: int, budget_ms: float = 2000.0) -> int:
    """Largest burst of simultaneous requests that all finish within budget_ms.

    Each request needs one core for service_ms (one intra-op thread); N requests on
    `cores` cores complete in ceil(N / cores) waves. A model for checking the measured
    numbers, not a substitute for them.
    """
    waves = int(budget_ms // service_ms)
    return waves * cores
