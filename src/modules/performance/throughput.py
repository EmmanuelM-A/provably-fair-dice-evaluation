import concurrent.futures
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from src.enigines.pfd import ProvablyFairDiceMechanism


@dataclass
class StartupSteadyStateResult:
    test_name: str
    n_requests: int
    cov_threshold: float
    startup_n: int
    startup_mean_ms: float
    startup_std_ms: float
    steady_state_n: int
    steady_state_mean_ms: float
    steady_state_std_ms: float
    steady_state_cov: float
    steady_state_declared_at: int  # index of first steady-state window; -1 if never reached


@dataclass
class ConcurrencyResult:
    concurrency: int
    actual_workers: int
    n_requests: int
    requests_per_second: float
    mean_latency_ms: float
    p99_latency_ms: float


def measure_startup_vs_steady_state(
    mechanism: ProvablyFairDiceMechanism,
    n_requests: int = 10_000,
    cov_threshold: float = 0.02,
    window_size: int = 100,
) -> StartupSteadyStateResult:
    """
    Measures per-call latency across n_requests sequential calls and partitions
    the series into a startup phase and a steady-state phase. Steady-state is
    declared at the first rolling window of window_size samples whose CoV falls
    below cov_threshold.
    """
    latencies_ms: List[float] = []
    for _ in range(n_requests):
        t0 = time.perf_counter()
        mechanism.generate_rolls(1)
        latencies_ms.append((time.perf_counter() - t0) * 1_000)

    steady_state_idx = -1
    for i in range(window_size, n_requests + 1):
        window = latencies_ms[i - window_size : i]
        mean = float(np.mean(window))
        if mean > 0 and (float(np.std(window)) / mean) < cov_threshold:
            steady_state_idx = i - window_size
            break

    startup = latencies_ms[:steady_state_idx] if steady_state_idx != -1 else latencies_ms
    steady = latencies_ms[steady_state_idx:] if steady_state_idx != -1 else []

    steady_mean = float(np.mean(steady)) if steady else 0.0
    steady_std = float(np.std(steady)) if steady else 0.0
    steady_cov = (steady_std / steady_mean) if steady_mean > 0 else 0.0

    return StartupSteadyStateResult(
        test_name="startup_vs_steady_state",
        n_requests=n_requests,
        cov_threshold=cov_threshold,
        startup_n=len(startup),
        startup_mean_ms=float(np.mean(startup)) if startup else 0.0,
        startup_std_ms=float(np.std(startup)) if startup else 0.0,
        steady_state_n=len(steady),
        steady_state_mean_ms=steady_mean,
        steady_state_std_ms=steady_std,
        steady_state_cov=steady_cov,
        steady_state_declared_at=steady_state_idx,
    )


def measure_throughput_under_load(
    mechanism: ProvablyFairDiceMechanism,
    concurrency_levels: Optional[List[int]] = None,
    n_requests: int = 200,
) -> Dict[int, ConcurrencyResult]:
    """
    Submits n_requests tasks at each concurrency level using a thread pool and
    measures wall-time throughput and per-request latency. actual_workers is
    capped at min(concurrency, n_requests, 512) to avoid OS thread limits.

    Note: for CPU-bound mechanisms (e.g. HMAC), Python's GIL limits true
    parallelism; throughput gains are only visible for I/O-bound mechanisms
    (e.g. drand, Chainlink VRF).
    """
    if concurrency_levels is None:
        concurrency_levels = [10, 100, 1_000, 10_000]

    def _roll(_: int) -> float:
        t0 = time.perf_counter()
        mechanism.generate_rolls(1)
        return (time.perf_counter() - t0) * 1_000

    results: Dict[int, ConcurrencyResult] = {}
    for concurrency in concurrency_levels:
        actual_workers = min(concurrency, n_requests, 512)
        wall_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as pool:
            latencies_ms = list(pool.map(_roll, range(n_requests)))
        wall_elapsed = time.perf_counter() - wall_start

        arr = np.array(latencies_ms)
        results[concurrency] = ConcurrencyResult(
            concurrency=concurrency,
            actual_workers=actual_workers,
            n_requests=n_requests,
            requests_per_second=n_requests / wall_elapsed,
            mean_latency_ms=float(np.mean(arr)),
            p99_latency_ms=float(np.percentile(arr, 99)),
        )

    return results
