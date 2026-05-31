from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.modules.data import BinaryResult
from src.modules.transparency.determinism import determinism_test
from src.modules.transparency.mapping_reproducibility import outcome_mapping_reproducibility
from src.utils.common_operations import rejection_sampling
from src.utils.types import RollRecord


# ---------------------------------------------------------------------------
# Tier-specific result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TransparencyLightEvaluationResult:
    """Determinism and outcome mapping reproducibility."""
    determinism: BinaryResult
    mapping_reproducibility: BinaryResult
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.summary = {
            "determinism": self.determinism.passed,
            "mapping_reproducibility": self.mapping_reproducibility.passed,
        }


@dataclass
class TransparencyInDepthEvaluationResult:
    """Reserved for future extension beyond LIGHT."""
    pass


@dataclass
class TransparencyFullDepthEvaluationResult:
    """Reserved for future extension beyond IN_DEPTH."""
    pass


# ---------------------------------------------------------------------------
# Top-level result wrapper
# ---------------------------------------------------------------------------

@dataclass
class TransparencyEvaluationResult:
    n_rolls: int
    light: Optional[TransparencyLightEvaluationResult] = None
    in_depth: Optional[TransparencyInDepthEvaluationResult] = None
    full_depth: Optional[TransparencyFullDepthEvaluationResult] = None


# ---------------------------------------------------------------------------
# Evaluation pipeline
# ---------------------------------------------------------------------------

class TransparencyTests:
    """
    Runs the full transparency test pipeline against a set of roll records.

    Three tiers of evaluation are available:

    LIGHT — determinism (end-to-end re-derivation) and outcome mapping
        reproducibility (mapping step in isolation).
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
        self,
        rolls: List[RollRecord],
        mechanism: ProvablyFairDiceMechanism,
        mapping_fn: Callable[[bytes], int],
    ) -> TransparencyLightEvaluationResult:
        """Determinism and outcome mapping reproducibility."""
        self._logger.info("Running determinism test...")
        det = determinism_test(rolls, mechanism)
        self._logger.info(det.message)

        self._logger.info("Running outcome mapping reproducibility test...")
        mapping = outcome_mapping_reproducibility(rolls, mapping_fn)
        self._logger.info(mapping.message)

        return TransparencyLightEvaluationResult(
            determinism=det,
            mapping_reproducibility=mapping,
        )

    def _run_in_depth_evaluation_framework(
        self, _rolls: List[RollRecord], _mechanism: ProvablyFairDiceMechanism
    ) -> TransparencyInDepthEvaluationResult:
        raise NotImplementedError("In-depth transparency evaluation not implemented yet.")

    def _run_full_depth_evaluation_framework(
        self, _rolls: List[RollRecord], _mechanism: ProvablyFairDiceMechanism
    ) -> TransparencyFullDepthEvaluationResult:
        raise NotImplementedError("Full depth transparency evaluation not implemented yet.")

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def run(
        self,
        rolls: List[RollRecord],
        mechanism: ProvablyFairDiceMechanism,
        mapping_fn: Optional[Callable[[bytes], int]] = None,
    ) -> TransparencyEvaluationResult:
        """
        Run the transparency evaluation pipeline for the configured tier.

        mapping_fn: the output-to-outcome mapping function used by the mechanism.
            Defaults to rejection_sampling. Override for mechanisms that use a
            different mapping step.
        """
        if mapping_fn is None:
            mapping_fn = rejection_sampling

        result = TransparencyEvaluationResult(n_rolls=len(rolls))

        result.light = self._run_light_evaluation_framework(rolls, mechanism, mapping_fn)

        if self._tier not in ["IN_DEPTH", "FULL_DEPTH"]:
            return result

        try:
            result.in_depth = self._run_in_depth_evaluation_framework(rolls, mechanism)
        except NotImplementedError:
            self._logger.warning("Transparency IN_DEPTH tier not implemented, skipping.")

        if self._tier not in ["FULL_DEPTH"]:
            return result

        try:
            result.full_depth = self._run_full_depth_evaluation_framework(rolls, mechanism)
        except NotImplementedError:
            self._logger.warning("Transparency FULL_DEPTH tier not implemented, skipping.")

        return result
