from dataclasses import dataclass, field
from typing import Any, Dict, List

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


@dataclass
class SecurityEvaluationResult:
    n_rolls: int
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


class SecurityTests:
    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config
        self._logger = BaseLogger(__name__)

    def run(self, rolls: List[RollRecord]) -> SecurityEvaluationResult:
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

        result = SecurityEvaluationResult(
            n_rolls=len(rolls),
            seed_reuse=seed_reuse,
            nonce_presence=nonce_presence,
            nonce_uniqueness=nonce_uniqueness,
            nonce_min_entropy=nonce_min_entropy,
        )
        return result
