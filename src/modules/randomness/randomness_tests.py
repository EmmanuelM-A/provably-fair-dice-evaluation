from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.enigines.config import EvaluationConfig
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
from src.modules.randomness.sanity_check import SanityCheckResult, assert_sanity_check
from src.utils.types import RollRecord


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


class RandomnessTests:
    """
    Runs the full randomness test pipeline against a set of roll records.

    Pipeline order:
    1. Framework sanity check: Halts if the test battery is miscalibrated.

    2. Distribution tests: Chi-square, Cramér-von Mises, runs independence.

    3. NIST SP 800-22: Light tier (tests 1–7) and/or in-depth (tests 8–10),
        determined by available bits from raw_output.

    4. Entropy monitoring: Repetition Count + Adaptive Proportion (NIST SP 800-90B).
    """

    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config
        self._logger = BaseLogger(__name__)

    def run(self, rolls: List[RollRecord]) -> RandomnessEvaluationResult:
        n_rolls = len(rolls)
        if n_rolls < self.config.distribution_min_rolls:
            raise ValueError(
                f"Randomness evaluation requires at least "
                f"{self.config.distribution_min_rolls} rolls. Got {n_rolls}."
            )

        # Step 1: sanity check — blocks if the test battery is miscalibrated.
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
            "chi_square": chi_square_test(outcomes, n_faces=self.config.n_faces),
            "cramer_von_mises": cramer_von_mises_test(outcomes),
            "runs_independence": runs_independence_test(outcomes),
        }

        # Step 3: NIST test battery — tier determined by available bits.
        nist_light: Optional[Dict[str, TestResult]] = None
        nist_in_depth: Optional[Dict[str, TestResult]] = None

        if n_bits >= self.config.nist_light_min_bits:
            self._logger.info("Running NIST light-tier tests (1–7)...")
            nist_light = LightEvaluationNistTests().run_all_tests(
                bit_sequence=raw_bytes,
                sequence_length=n_bits,
            )
        else:
            self._logger.warning(
                f"NIST light tier skipped: {n_bits} bits available, "
                f"{self.config.nist_light_min_bits} required "
                f"({self.config.nist_light_min_bits // 8} bytes of raw output)."
            )

        if n_bits >= self.config.nist_in_depth_min_bits:
            self._logger.info("Running NIST in-depth tier tests (8–10)...")
            nist_in_depth = InDepthEvaluationNistTests().run_all_tests(
                bit_sequence=raw_bytes,
                sequence_length=self.config.nist_in_depth_min_bits,
            )

        # Step 4: entropy monitoring.
        self._logger.info("Running entropy monitoring...")
        window_w = min(self.config.adaptive_window_w, n_rolls)
        entropy_monitoring: Dict[str, MonitorResult] = {
            "repetition_count": repetition_count_test(
                samples=outcomes,
                threshold_c=self.config.repetition_threshold_c,
            ),
            "adaptive_proportion": adaptive_proportion_test(
                samples=outcomes,
                window_w=window_w,
                threshold=self.config.adaptive_threshold,
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
        return result
