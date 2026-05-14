import time
from dataclasses import dataclass
from typing import List

import numpy as np

from src.enigines.pfd import ProvablyFairDiceMechanism


@dataclass
class LatencyResult:
    test_name: str
    n_requests: int
    mean_ms: float
    median_ms: float
    p75_ms: float
    p90_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_ms: float


def measure_dice_generation_latency(
    mechanism: ProvablyFairDiceMechanism,
    n_requests: int = 1_000,
) -> LatencyResult:
    """
    Times each individual generate_rolls(1) call sequentially.
    Returns summary statistics of the resulting latency distribution.
    """
    latencies_ms: List[float] = []
    for _ in range(n_requests):
        t0 = time.perf_counter()
        mechanism.generate_rolls(1)
        latencies_ms.append((time.perf_counter() - t0) * 1_000)

    arr = np.array(latencies_ms)
    return LatencyResult(
        test_name="dice_generation_latency",
        n_requests=n_requests,
        mean_ms=float(np.mean(arr)),
        median_ms=float(np.median(arr)),
        p75_ms=float(np.percentile(arr, 75)),
        p90_ms=float(np.percentile(arr, 90)),
        p99_ms=float(np.percentile(arr, 99)),
        min_ms=float(np.min(arr)),
        max_ms=float(np.max(arr)),
        std_ms=float(np.std(arr)),
    )
