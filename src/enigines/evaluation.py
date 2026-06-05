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
    tier: str
    saved_at: str
    halted_at: Optional[str] = None  # "LIGHT" or "IN_DEPTH" if a gate fired early
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

    def _save(self, result: EvaluationResult) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self._results_file_path)), exist_ok=True)
        with open(self._results_file_path, "w", encoding="utf-8") as f:
            json.dump(result.to_json(), f, cls=_JsonEncoder, indent=4)
        self._logger.info(f"Results saved to {self._results_file_path}")

    def _light_gate_passes(self, result: EvaluationResult) -> bool:
        """Gate 1: halt progression to IN_DEPTH if nonce presence fails."""
        if result.security and result.security.light:
            return result.security.light.nonce_presence.passed
        return True

    def _in_depth_gate_passes(self, result: EvaluationResult) -> bool:
        """Gate 2: halt progression to FULL_DEPTH if entropy monitoring has alarms."""
        if result.randomness and result.randomness.in_depth:
            em = result.randomness.in_depth.entropy_monitoring
            if em:
                rep = em.get("repetition_count")
                adp = em.get("adaptive_proportion")
                if rep is not None and not rep.passed:
                    return False
                if adp is not None and not adp.passed:
                    return False
        return True

    def run_evaluation(
        self,
        rolls: List[RollRecord],
        tier: Literal["LIGHT", "IN_DEPTH", "FULL_DEPTH"],
        mapping_fn: Optional[Callable[[bytes], float]] = None,
    ) -> EvaluationResult:
        self._logger.info(f"Starting {tier} evaluation for mechanism: {self._mechanism}")

        result = EvaluationResult(
            mechanism=str(self._mechanism),
            tier=tier,
            saved_at=datetime.now(timezone.utc).strftime(DATE_FORMAT),
            performance=PerformanceEvaluationResult(),
        )

        # Phase 1: always run LIGHT for all domains
        result.randomness = RandomnessTests(self._config, "LIGHT", self._mechanism).run(rolls)
        result.security = SecurityTests(self._config, "LIGHT").run(rolls)
        # result.performance = PerformanceTests(self._config, "LIGHT").run(
        #     mechanism=self._mechanism,
        #     n_latency_requests=self._config.n_latency_requests,
        # )
        result.transparency = TransparencyTests(self._config, "LIGHT").run(
            rolls=rolls,
            mechanism=self._mechanism,
            mapping_fn=mapping_fn,
        )

        # Gate 1: halt if nonce presence fails
        if not self._light_gate_passes(result):
            self._logger.warning("Gate 1 fired: nonce_presence failed — halting at LIGHT.")
            result.halted_at = "LIGHT"
            self._save(result)
            return result

        if tier not in ("IN_DEPTH", "FULL_DEPTH"):
            self._save(result)
            return result

        # Phase 2: run IN_DEPTH (splice only the in_depth parts)
        self._logger.info("Progressing to IN_DEPTH evaluation...")

        in_depth_randomness = RandomnessTests(self._config, "IN_DEPTH", self._mechanism).run(rolls)
        result.randomness.in_depth = in_depth_randomness.in_depth

        # Gate 2: halt if entropy monitoring has alarms
        if not self._in_depth_gate_passes(result):
            self._logger.warning("Gate 2 fired: entropy monitoring alarms — halting at IN_DEPTH.")
            result.halted_at = "IN_DEPTH"
            self._save(result)
            return result

        in_depth_performance = PerformanceTests(self._config, "IN_DEPTH").run(
            mechanism=self._mechanism,
            n_latency_requests=self._config.n_latency_requests,
            n_startup_requests=self._config.n_startup_requests,
            n_load_requests=self._config.n_load_requests,
        )
        # result.performance.in_depth = in_depth_performance.in_depth

        if tier not in ("FULL_DEPTH",):
            self._save(result)
            return result

        # Phase 3: attempt FULL_DEPTH (each class catches NotImplementedError internally)
        self._logger.info("Progressing to FULL_DEPTH evaluation...")
        try:
            full_depth_randomness = RandomnessTests(self._config, "FULL_DEPTH", self._mechanism).run(rolls)
            result.randomness.full_depth = full_depth_randomness.full_depth
        except NotImplementedError:
            self._logger.warning("Randomness FULL_DEPTH not implemented, skipping.")

        self._save(result)
        return result
