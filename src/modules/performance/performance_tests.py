from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.modules.performance.latency import LatencyResult, measure_dice_generation_latency
from src.modules.performance.throughput import (
    ConcurrencyResult,
    StartupSteadyStateResult,
    measure_startup_vs_steady_state,
    measure_throughput_under_load,
)


# ---------------------------------------------------------------------------
# Tier-specific result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PerformanceLightEvaluationResult:
    """Latency distribution across sequential generate_rolls calls."""
    latency: LatencyResult
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.summary = {
            "mean_latency_ms": round(self.latency.mean_ms, 4),
            "p99_latency_ms": round(self.latency.p99_ms, 4),
        }


@dataclass
class PerformanceInDepthEvaluationResult:
    """Startup vs steady-state and throughput under concurrent load."""
    startup_steady_state: StartupSteadyStateResult
    throughput_under_load: Dict[int, ConcurrencyResult]
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        peak_rps = max(
            (r.requests_per_second for r in self.throughput_under_load.values()),
            default=0.0,
        )
        self.summary = {
            "steady_state_reached": self.startup_steady_state.steady_state_declared_at != -1,
            "steady_state_mean_ms": round(self.startup_steady_state.steady_state_mean_ms, 4),
            "peak_requests_per_second": round(peak_rps, 2),
        }


@dataclass
class PerformanceFullDepthEvaluationResult:
    """Reserved for future extension beyond IN_DEPTH."""
    pass


# ---------------------------------------------------------------------------
# Top-level result wrapper
# ---------------------------------------------------------------------------

@dataclass
class PerformanceEvaluationResult:
    light: Optional[PerformanceLightEvaluationResult] = None
    in_depth: Optional[PerformanceInDepthEvaluationResult] = None
    full_depth: Optional[PerformanceFullDepthEvaluationResult] = None


# ---------------------------------------------------------------------------
# Evaluation pipeline
# ---------------------------------------------------------------------------

class PerformanceTests:
    """
    Runs the full performance test pipeline against a mechanism.

    Three tiers of evaluation are available:

    LIGHT — latency distribution (mean, p75, p90, p99) across sequential calls.
    IN_DEPTH — LIGHT plus startup vs steady-state detection and throughput under
        concurrent load at multiple concurrency levels.
    FULL_DEPTH — reserved for future extension.
    """

    def __init__(
        self, config: EvaluationConfig, tier: Literal["LIGHT", "IN_DEPTH", "FULL_DEPTH"]
    ) -> None:
        self.config = config
        self._tier = tier
        self._logger = BaseLogger(__name__)

    # -------------------------------------------------------------------------
    # Tier implementations
    # -------------------------------------------------------------------------

    def _run_light_evaluation_framework(
        self,
        mechanism: ProvablyFairDiceMechanism,
        n_latency_requests: int,
    ) -> PerformanceLightEvaluationResult:
        """Latency distribution across n_latency_requests sequential calls."""
        self._logger.info(f"Measuring dice generation latency ({n_latency_requests} requests)...")
        latency = measure_dice_generation_latency(mechanism, n_requests=n_latency_requests)
        self._logger.info(
            f"Latency — mean: {latency.mean_ms:.3f}ms, "
            f"median: {latency.median_ms:.3f}ms, "
            f"p99: {latency.p99_ms:.3f}ms."
        )
        return PerformanceLightEvaluationResult(latency=latency)

    def _run_in_depth_evaluation_framework(
        self,
        mechanism: ProvablyFairDiceMechanism,
        n_startup_requests: int,
        n_load_requests: int,
    ) -> PerformanceInDepthEvaluationResult:
        """Startup vs steady-state and throughput under load.
        Assumes LIGHT has already run — does not repeat latency measurement."""
        self._logger.info(f"Measuring startup vs steady-state ({n_startup_requests} requests)...")
        startup_steady = measure_startup_vs_steady_state(mechanism, n_requests=n_startup_requests)
        if startup_steady.steady_state_declared_at != -1:
            self._logger.info(
                f"Steady-state declared at request {startup_steady.steady_state_declared_at} "
                f"(mean: {startup_steady.steady_state_mean_ms:.3f}ms)."
            )
        else:
            self._logger.warning(
                "Steady-state CoV threshold never reached within the measurement window."
            )

        self._logger.info(f"Measuring throughput under load ({n_load_requests} requests per level)...")
        load_results = measure_throughput_under_load(mechanism, n_requests=n_load_requests)
        for concurrency, result in load_results.items():
            self._logger.info(
                f"  concurrency={concurrency} (workers={result.actual_workers}): "
                f"{result.requests_per_second:.1f} req/s, "
                f"mean={result.mean_latency_ms:.3f}ms, p99={result.p99_latency_ms:.3f}ms."
            )

        return PerformanceInDepthEvaluationResult(
            startup_steady_state=startup_steady,
            throughput_under_load=load_results,
        )

    def _run_full_depth_evaluation_framework(
        self, _mechanism: ProvablyFairDiceMechanism
    ) -> PerformanceFullDepthEvaluationResult:
        raise NotImplementedError("Full depth performance evaluation not implemented yet.")

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def run(
        self,
        mechanism: ProvablyFairDiceMechanism,
        n_latency_requests: int = 1_000,
        n_startup_requests: int = 10_000,
        n_load_requests: int = 200,
    ) -> PerformanceEvaluationResult:
        """Run the performance evaluation pipeline for the configured tier."""
        result = PerformanceEvaluationResult()

        result.light = self._run_light_evaluation_framework(mechanism, n_latency_requests)

        if self._tier not in ["IN_DEPTH", "FULL_DEPTH"]:
            return result

        result.in_depth = self._run_in_depth_evaluation_framework(
            mechanism, n_startup_requests, n_load_requests
        )

        if self._tier not in ["FULL_DEPTH"]:
            return result

        result.full_depth = self._run_full_depth_evaluation_framework(mechanism)

        return result
