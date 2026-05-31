from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from src.enigines.config import EvaluationConfig
from src.logger.base_logger import BaseLogger
from src.modules.data import BinaryResult
from src.modules.security.nonce_checks import (
    check_nonce_presence,
    check_nonce_unpredictability,
    check_nonce_uniqueness,
)
from src.modules.security.seed_checks import check_seed_reuse
from src.utils.types import RollRecord


# ---------------------------------------------------------------------------
# Tier-specific result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SecurityLightEvaluationResult:
    """Seed reuse, nonce presence, nonce uniqueness, and nonce min-entropy."""
    seed_reuse: BinaryResult
    nonce_presence: BinaryResult
    nonce_uniqueness: BinaryResult
    nonce_min_entropy: float
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.summary = {
            "seed_reuse": self.seed_reuse.passed,
            "nonce_presence": self.nonce_presence.passed,
            "nonce_uniqueness": self.nonce_uniqueness.passed,
            "nonce_min_entropy_bits": round(self.nonce_min_entropy, 4),
        }


@dataclass
class SecurityInDepthEvaluationResult:
    """Reserved for future extension beyond LIGHT."""
    pass


@dataclass
class SecurityFullDepthEvaluationResult:
    """Reserved for future extension beyond IN_DEPTH."""
    pass


# ---------------------------------------------------------------------------
# Top-level result wrapper
# ---------------------------------------------------------------------------

@dataclass
class SecurityEvaluationResult:
    n_rolls: int
    light: Optional[SecurityLightEvaluationResult] = None
    in_depth: Optional[SecurityInDepthEvaluationResult] = None
    full_depth: Optional[SecurityFullDepthEvaluationResult] = None


# ---------------------------------------------------------------------------
# Evaluation pipeline
# ---------------------------------------------------------------------------

class SecurityTests:
    """
    Runs the full security test pipeline against a set of roll records.

    Three tiers of evaluation are available:

    LIGHT — seed reuse, nonce presence, nonce uniqueness, and nonce min-entropy.
    IN_DEPTH — reserved for future extension.
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
        self, rolls: List[RollRecord]
    ) -> SecurityLightEvaluationResult:
        """Seed reuse, nonce presence, nonce uniqueness, and nonce min-entropy."""
        self._logger.info("Running seed reuse check...")
        seed_reuse = check_seed_reuse(rolls)
        self._logger.info(seed_reuse.message)

        self._logger.info("Running nonce checks...")
        nonce_presence = check_nonce_presence(rolls)
        self._logger.info(nonce_presence.message)
        nonce_uniqueness = check_nonce_uniqueness(rolls)
        self._logger.info(nonce_uniqueness.message)
        nonce_min_entropy = check_nonce_unpredictability(rolls)
        self._logger.info(f"Nonce min-entropy: {nonce_min_entropy:.4f} bits.")

        return SecurityLightEvaluationResult(
            seed_reuse=seed_reuse,
            nonce_presence=nonce_presence,
            nonce_uniqueness=nonce_uniqueness,
            nonce_min_entropy=nonce_min_entropy,
        )

    def _run_in_depth_evaluation_framework(
        self, _rolls: List[RollRecord]
    ) -> SecurityInDepthEvaluationResult:
        raise NotImplementedError("In-depth security evaluation not implemented yet.")

    def _run_full_depth_evaluation_framework(
        self, _rolls: List[RollRecord]
    ) -> SecurityFullDepthEvaluationResult:
        raise NotImplementedError("Full depth security evaluation not implemented yet.")

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def run(self, rolls: List[RollRecord]) -> SecurityEvaluationResult:
        """Run the security evaluation pipeline for the configured tier."""
        result = SecurityEvaluationResult(n_rolls=len(rolls))

        result.light = self._run_light_evaluation_framework(rolls)

        if self._tier not in ["IN_DEPTH", "FULL_DEPTH"]:
            return result

        try:
            result.in_depth = self._run_in_depth_evaluation_framework(rolls)
        except NotImplementedError:
            self._logger.warning("Security IN_DEPTH tier not implemented, skipping.")

        if self._tier not in ["FULL_DEPTH"]:
            return result

        try:
            result.full_depth = self._run_full_depth_evaluation_framework(rolls)
        except NotImplementedError:
            self._logger.warning("Security FULL_DEPTH tier not implemented, skipping.")

        return result
