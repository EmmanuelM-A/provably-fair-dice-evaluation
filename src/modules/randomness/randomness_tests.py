from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

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
from src.modules.randomness.sanity_check import SanityCheckResult, run_sanity_check
from src.utils.types import RollRecord


# ---------------------------------------------------------------------------
# Tier-specific result dataclasses (each extends the previous)
# ---------------------------------------------------------------------------

@dataclass
class RandomnessLightEvaluationResult:
    """Results produced by the LIGHT evaluation tier."""
    sanity_check: SanityCheckResult
    chi_square: TestResult
    nist_light: Optional[Dict[str, TestResult]] = None


@dataclass
class RandomnessInDepthEvaluationResult:
    """Cramér-von Mises, runs independence, NIST tests 8-10, and entropy monitoring."""
    cramer_von_mises: TestResult
    runs_independence: TestResult
    entropy_monitoring: Dict[str, MonitorResult] = field(default_factory=dict)
    nist_in_depth: Optional[Dict[str, TestResult]] = None


@dataclass
class RandomnessFullDepthEvaluationResult:
    """Reserved for future extension beyond IN_DEPTH."""
    pass


# ---------------------------------------------------------------------------
# Top-level result wrapper
# ---------------------------------------------------------------------------

@dataclass
class RandomnessEvaluationResult:
    n_rolls: int
    n_bits: int
    light: Optional[RandomnessLightEvaluationResult] = None
    in_depth: Optional[RandomnessInDepthEvaluationResult] = None
    full_depth: Optional[RandomnessFullDepthEvaluationResult] = None


# ---------------------------------------------------------------------------
# Evaluation pipeline
# ---------------------------------------------------------------------------

class RandomnessTests:
    """
    Runs the full randomness test pipeline against a set of roll records.

    Three tiers of evaluation are available:

    LIGHT — sanity check + chi-square uniformity + NIST SP 800-22 tests 1-7.
    IN_DEPTH — LIGHT plus Cramér-von Mises, runs independence, NIST tests 8-10,
        and runtime entropy monitoring (NIST SP 800-90B).
    FULL_DEPTH — reserved for future extension.
    """

    def __init__(
        self, config: EvaluationConfig, tier: Literal["LIGHT", "IN_DEPTH", "FULL_DEPTH"]
    ) -> None:
        self.config = config
        self._tier = tier
        self._logger = BaseLogger(__name__)

    # -------------------------------------------------------------------------
    # Shared helpers
    # -------------------------------------------------------------------------

    def _validate_rolls(self, rolls: List[RollRecord]) -> None:
        n = len(rolls)
        if n < self.config.distribution_min_rolls:
            raise ValueError(
                f"Randomness evaluation requires at least "
                f"{self.config.distribution_min_rolls} rolls. Got {n}."
            )

    def _run_sanity_check(self, rolls: List[RollRecord]) -> SanityCheckResult:
        self._logger.info("Running framework sanity check...")
        result = run_sanity_check(configs=self.config)
        self._logger.info(result.message)
        return result

    def _extract_bits(self, rolls: List[RollRecord]) -> tuple[List[int], bytes, int]:
        outcomes = [r.outcome for r in rolls]
        raw_bytes = b"".join(r.raw_output for r in rolls)
        n_bits = len(raw_bytes) * 8
        return outcomes, raw_bytes, n_bits

    # -------------------------------------------------------------------------
    # Tier implementations
    # -------------------------------------------------------------------------

    def _run_light_evaluation_framework(
        self, rolls: List[RollRecord]
    ) -> RandomnessLightEvaluationResult:
        """Sanity check + chi-square uniformity + NIST SP 800-22 tests 1-7."""
        self._validate_rolls(rolls)
        sanity = self._run_sanity_check(rolls)
        outcomes, raw_bytes, n_bits = self._extract_bits(rolls)

        self._logger.info("Running distribution tests (light)...")
        chi_square = chi_square_test(outcomes, self.config, n_faces=self.config.n_faces)

        nist_light: Optional[Dict[str, TestResult]] = None
        if n_bits >= self.config.nist_light_min_bits:
            self._logger.info("Running NIST light-tier tests (1-7)...")
            nist_light = LightEvaluationNistTests().run_all_tests(
                bit_sequence=raw_bytes,
                sequence_length=n_bits,
                configs=self.config,
            )
        else:
            self._logger.warning(
                f"NIST light tier skipped: {n_bits} bits available, "
                f"{self.config.nist_light_min_bits} required."
            )

        return RandomnessLightEvaluationResult(
            sanity_check=sanity,
            chi_square=chi_square,
            nist_light=nist_light,
        )

    def _run_in_depth_evaluation_framework(
        self, rolls: List[RollRecord]
    ) -> RandomnessInDepthEvaluationResult:
        """Cramér-von Mises, runs independence, NIST tests 8-10, entropy monitoring.
        Assumes LIGHT has already run — does not repeat sanity check, chi-square,
        or NIST light tests."""
        outcomes, raw_bytes, n_bits = self._extract_bits(rolls)

        self._logger.info("Running in-depth distribution tests...")
        cramer_von_mises = cramer_von_mises_test(outcomes, self.config)
        runs_independence = runs_independence_test(outcomes, self.config)

        nist_in_depth: Optional[Dict[str, TestResult]] = None
        if n_bits >= self.config.nist_in_depth_min_bits:
            self._logger.info("Running NIST in-depth tier tests (8-10)...")
            nist_in_depth = InDepthEvaluationNistTests().run_all_tests(
                bit_sequence=raw_bytes,
                sequence_length=n_bits,
                configs=self.config,
            )
        else:
            self._logger.warning(
                f"NIST in-depth tier skipped: {n_bits} bits available, "
                f"{self.config.nist_in_depth_min_bits} required."
            )

        self._logger.info("Running entropy monitoring...")
        window_w = min(self.config.adaptive_window_w, len(rolls))
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

        return RandomnessInDepthEvaluationResult(
            cramer_von_mises=cramer_von_mises,
            runs_independence=runs_independence,
            nist_in_depth=nist_in_depth,
            entropy_monitoring=entropy_monitoring,
        )

    def _run_full_depth_evaluation_framework(
        self, _rolls: List[RollRecord]
    ) -> RandomnessFullDepthEvaluationResult:
        raise NotImplementedError("Full depth evaluation framework not implemented yet.")

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def run(self, rolls: List[RollRecord]) -> RandomnessEvaluationResult:
        """Run the randomness evaluation pipeline for the configured tier."""
        _, _, n_bits = self._extract_bits(rolls)
        n_rolls = len(rolls)
        
        result = RandomnessEvaluationResult(n_rolls=n_rolls, n_bits=n_bits)
        
        result.light = self._run_light_evaluation_framework(rolls)
        
        if self._tier not in ["IN_DEPTH", "FULL_DEPTH"]:
            return result
        
        result.in_depth = self._run_in_depth_evaluation_framework(rolls)
        
        if self._tier not in ["FULL_DEPTH"]:
            return result
        
        result.full_depth = self._run_full_depth_evaluation_framework(rolls)
        
        return result
