import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, List, Literal, Optional

import numpy as np

from src.config.configs import DATE_FORMAT
from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.modules.performance.performance_tests import PerformanceEvaluationResult, PerformanceTests
from src.modules.randomness.randomness_tests import RandomnessEvaluationResult, RandomnessTests
from src.modules.security.security_tests import SecurityEvaluationResult, SecurityTests
from src.modules.transparency.transparency_tests import TransparencyEvaluationResult, TransparencyTests
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


@dataclass
class EvaluationResult:
    """Aggregates results from all evaluation categories."""
    mechanism: str
    saved_at: str
    randomness: Optional[RandomnessEvaluationResult] = None
    security: Optional[SecurityEvaluationResult] = None
    performance: Optional[PerformanceEvaluationResult] = None
    transparency: Optional[TransparencyEvaluationResult] = None

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


class EvaluationEngine:
    def __init__(
        self,
        mechanism: ProvablyFairDiceMechanism,
        results_file_path: str,
        config: EvaluationConfig = EvaluationConfig(),
    ) -> None:
        self._mechanism = mechanism
        self._config = config
        self._results_file_path = results_file_path
        self._logger = BaseLogger(__name__)

    def run_evaluation(
        self,
        rolls: List[RollRecord],
        tier: Literal["LIGHT", "IN_DEPTH", "FULL_DEPTH"],
        mapping_fn: Optional[Callable[[bytes], int]] = None,
    ) -> EvaluationResult:
        self._logger.info(f"Starting {tier} evaluation for mechanism: {self._mechanism}")

        result = EvaluationResult(
            mechanism=str(self._mechanism),
            saved_at=datetime.now(timezone.utc).strftime(DATE_FORMAT),
        )

        result.randomness = RandomnessTests(self._config, tier).run(rolls)
        result.security = SecurityTests(self._config, tier).run(rolls)
        result.performance = PerformanceTests(self._config, tier).run(
            mechanism=self._mechanism,
            n_latency_requests=self._config.n_latency_requests,
            n_startup_requests=self._config.n_startup_requests,
            n_load_requests=self._config.n_load_requests,
        )
        result.transparency = TransparencyTests(self._config, tier).run(
            rolls=rolls,
            mechanism=self._mechanism,
            mapping_fn=mapping_fn,
        )

        os.makedirs(os.path.dirname(os.path.abspath(self._results_file_path)), exist_ok=True)
        with open(self._results_file_path, "w", encoding="utf-8") as f:
            json.dump(result.to_json(), f, cls=_JsonEncoder, indent=4)

        self._logger.info(f"Results saved to {self._results_file_path}")

        return result
