from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.modules.data import TestResult
from src.modules.randomness.distribution_tests import (
    chi_square_test,
    cramer_von_mises_test,
    runs_independence_test,
)
from src.modules.randomness.entropy_monitoring import (
    MonitorResult,
    adaptive_proportion_test,
    repetition_count_test,
)
from src.modules.randomness.nist_tests import (
    InDepthEvaluationNistTests,
    LightEvaluationNistTests,
)
from src.modules.randomness.sanity_check import (
    SanityCheckResult,
    assert_sanity_check,
)
from src.utils.types import RollRecord


_DISTRIBUTION_MIN_ROLLS = 500
_NIST_LIGHT_MIN_BITS = 20_000
_NIST_IN_DEPTH_MIN_BITS = 1_000_000

# Entropy monitoring defaults for a 6-face die.
# threshold_c = 20: conservative C = ceil(1/H) for H = log2(6) ≈ 2.58 bits.
# window_w = 512 and threshold = 120: threshold sits at ~99th percentile
# of the binomial count distribution under uniformity (expected ~85 per window).
_REPETITION_THRESHOLD_C = 20
_ADAPTIVE_WINDOW_W = 512
_ADAPTIVE_THRESHOLD = 120


@dataclass
class RandomnessEvaluationResult:
    n_rolls: int
    n_bits: int
    sanity_check: SanityCheckResult
    distribution: Dict[str, TestResult]
    nist_light: Optional[Dict[str, TestResult]]
    nist_in_depth: Optional[Dict[str, TestResult]]
    entropy_monitoring: Dict[str, MonitorResult]
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        passed: Dict[str, Any] = {
            "sanity_check": self.sanity_check.passed,
            "chi_square": self.distribution["chi_square"].passed,
            "cramer_von_mises": self.distribution["cramer_von_mises"].passed,
            "runs_independence": self.distribution["runs_independence"].passed,
            "repetition_count": self.entropy_monitoring["repetition_count"].passed,
            "adaptive_proportion": self.entropy_monitoring["adaptive_proportion"].passed,
        }
        if self.nist_light is not None:
            passed["nist_light_all_passed"] = all(
                r.passed for r in self.nist_light.values()
            )
        if self.nist_in_depth is not None:
            passed["nist_in_depth_all_passed"] = all(
                r.passed for r in self.nist_in_depth.values()
            )
        self.summary = passed


class EvaluationEngine:
    def __init__(self, mechanism: ProvablyFairDiceMechanism):
        self.mechanism = mechanism
        self._logger = BaseLogger(__name__)

    def evaluate_randomness(self, rolls: List[RollRecord]) -> RandomnessEvaluationResult:
        n_rolls = len(rolls)
        if n_rolls < _DISTRIBUTION_MIN_ROLLS:
            raise ValueError(
                f"Randomness evaluation requires at least {_DISTRIBUTION_MIN_ROLLS} rolls. "
                f"Got {n_rolls}."
            )

        # Step 1: framework sanity check — blocks if the test battery is miscalibrated.
        self._logger.info("Running framework sanity check...")
        sanity = assert_sanity_check()
        self._logger.info(sanity.message)

        outcomes: List[int] = [r.outcome for r in rolls]
        raw_bytes: bytes = b"".join(r.raw_output for r in rolls)
        n_bits = len(raw_bytes) * 8
        self._logger.info(f"Evaluating randomness: {n_rolls} rolls, {n_bits} bits.")

        # Step 2: distribution tests.
        self._logger.info("Running distribution tests...")
        distribution: Dict[str, TestResult] = {
            "chi_square": chi_square_test(outcomes),
            "cramer_von_mises": cramer_von_mises_test(outcomes),
            "runs_independence": runs_independence_test(outcomes),
        }

        # Step 3: NIST test battery — tier is determined by available bits.
        nist_light: Optional[Dict[str, TestResult]] = None
        nist_in_depth: Optional[Dict[str, TestResult]] = None

        if n_bits >= _NIST_LIGHT_MIN_BITS:
            self._logger.info("Running NIST light-tier tests (1–7)...")
            nist_light = LightEvaluationNistTests().run_all_tests(
                bit_sequence=raw_bytes,
                sequence_length=n_bits,
            )
        else:
            self._logger.warning(
                f"NIST light tier skipped: {n_bits} bits available, "
                f"{_NIST_LIGHT_MIN_BITS} required "
                f"({_NIST_LIGHT_MIN_BITS // 8} bytes of raw output)."
            )

        if n_bits >= _NIST_IN_DEPTH_MIN_BITS:
            self._logger.info("Running NIST in-depth tier tests (8–10)...")
            nist_in_depth = InDepthEvaluationNistTests().run_all_tests(
                bit_sequence=raw_bytes,
                sequence_length=_NIST_IN_DEPTH_MIN_BITS,
            )

        # Step 4: runtime entropy monitoring.
        self._logger.info("Running entropy monitoring...")
        window_w = min(_ADAPTIVE_WINDOW_W, n_rolls)
        entropy_monitoring: Dict[str, MonitorResult] = {
            "repetition_count": repetition_count_test(
                samples=outcomes,
                threshold_c=_REPETITION_THRESHOLD_C,
            ),
            "adaptive_proportion": adaptive_proportion_test(
                samples=outcomes,
                window_w=window_w,
                threshold=_ADAPTIVE_THRESHOLD,
            ),
        }

        result = RandomnessEvaluationResult(
            n_rolls=n_rolls,
            n_bits=n_bits,
            sanity_check=sanity,
            distribution=distribution,
            nist_light=nist_light,
            nist_in_depth=nist_in_depth,
            entropy_monitoring=entropy_monitoring,
        )

        self._logger.info(f"Randomness evaluation complete. Summary: {result.summary}")
        return result

    def evaluate_security(self):
        pass

    def evaluate_performance(self):
        pass

    def evaluate_transparency(self):
        pass
