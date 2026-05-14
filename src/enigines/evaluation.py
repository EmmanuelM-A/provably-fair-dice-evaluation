import dataclasses
import json
import os
from datetime import datetime, timezone
from typing import Any, List, Optional

import numpy as np

from src.config.configs import DATE_FORMAT
from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.modules.randomness.randomness_tests import RandomnessEvaluationResult, RandomnessTests
from src.modules.security.security_tests import SecurityEvaluationResult, SecurityTests
from src.utils.types import RollRecord


class _JsonEncoder(json.JSONEncoder):
    """Handles numpy scalars, numpy arrays, dataclasses, and datetimes."""

    def default(self, o: Any) -> Any:
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, datetime):
            return o.isoformat()
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return super().default(o)


class EvaluationEngine:
    def __init__(
        self,
        mechanism: ProvablyFairDiceMechanism,
        config: EvaluationConfig = EvaluationConfig(),
    ) -> None:
        self.mechanism = mechanism
        self.config = config
        self._logger = BaseLogger(__name__)
        self._randomness_result: Optional[RandomnessEvaluationResult] = None
        self._security_result: Optional[SecurityEvaluationResult] = None

    def evaluate_randomness(self, rolls: List[RollRecord]) -> RandomnessEvaluationResult:
        result = RandomnessTests(self.config).run(rolls)
        self._randomness_result = result
        return result

    def evaluate_security(self, rolls: List[RollRecord]) -> SecurityEvaluationResult:
        result = SecurityTests(self.config).run(rolls)
        self._security_result = result
        return result

    def evaluate_performance(self) -> None:
        pass

    def evaluate_transparency(self) -> None:
        pass

    def save_results(self, path: str) -> None:
        """
        Serialise all completed evaluation results to a JSON file.

        Output schema:
        {
            "mechanism":   "<mechanism_id>",
            "saved_at":    "%Y-%m-%d %H:%M:%S",
            "randomness":  { ... } | null,
            "security":    { ... } | null,
            "performance": null,
            "transparency": null
        }
        """
        payload: dict[str, Any] = {
            "mechanism": str(self.mechanism),
            "saved_at": datetime.now(timezone.utc).strftime(DATE_FORMAT),
            "randomness": (
                dataclasses.asdict(self._randomness_result)
                if self._randomness_result is not None
                else None
            ),
            "security": (
                dataclasses.asdict(self._security_result)
                if self._security_result is not None
                else None
            ),
            "performance": None,
            "transparency": None,
        }

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, cls=_JsonEncoder, indent=2)

        self._logger.info(f"Results saved to {path}")
