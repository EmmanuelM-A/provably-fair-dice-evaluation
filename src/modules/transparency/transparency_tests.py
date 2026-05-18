from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.modules.data import BinaryResult
from src.modules.transparency.determinism import determinism_test
from src.modules.transparency.mapping_reproducibility import outcome_mapping_reproducibility
from src.utils.common_operations import rejection_sampling
from src.utils.types import RollRecord


@dataclass
class TransparencyEvaluationResult:
    n_rolls: int
    determinism: BinaryResult
    mapping_reproducibility: BinaryResult
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.summary = {
            "determinism": self.determinism.passed,
            "mapping_reproducibility": self.mapping_reproducibility.passed,
        }


class TransparencyTests:
    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config
        self._logger = BaseLogger(__name__)

    def run(
        self,
        rolls: List[RollRecord],
        mechanism: ProvablyFairDiceMechanism,
        mapping_fn: Optional[Callable[[bytes], int]] = None,
    ) -> TransparencyEvaluationResult:
        """
        Runs the two programmable transparency tests against a set of roll records.

        mapping_fn: the output-to-outcome mapping function used by the mechanism.
            Defaults to rejection_sampling (HMAC mechanism). Override for drand
            or Chainlink VRF mechanisms that use a different mapping step.
        """
        if mapping_fn is None:
            mapping_fn = rejection_sampling

        self._logger.info("Running determinism test...")
        det = determinism_test(rolls, mechanism)
        self._logger.info(det.message)

        self._logger.info("Running outcome mapping reproducibility test...")
        mapping = outcome_mapping_reproducibility(rolls, mapping_fn)
        self._logger.info(mapping.message)

        return TransparencyEvaluationResult(
            n_rolls=len(rolls),
            determinism=det,
            mapping_reproducibility=mapping,
        )
