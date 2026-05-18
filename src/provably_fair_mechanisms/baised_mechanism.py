"""
A biased die mechanism used as a negative control in randomness evaluations.
"""

from datetime import datetime, timezone
from typing import List

import numpy as np

from src.config.configs import SEED
from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.utils.types import RollRecord, VerificationResult


class BiasedMechanism(ProvablyFairDiceMechanism):
    """
    A non-provably-fair biased die mechanism used as a negative control.

    Outcomes are drawn from a skewed distribution (P(6) = 1/3, P(1-5) = 2/15)
    rather than a uniform one, so the randomness evaluation should flag it.
    """

    MECHANISM_ID = "biased"

    def __init__(self, config: EvaluationConfig) -> None:
        self._rng = np.random.default_rng(SEED)
        self.config = config
        self._BIASED_PROBS: list[float] = [2 / 15] * 5 + [1 / 3]

    # ========================= Randomness Generation =========================

    def generate_rolls(
        self, quantity: int, save_rolls: bool = True
    ) -> List[RollRecord]:
        outcomes = self._rng.choice(self.config.n_faces, size=quantity, p=self._BIASED_PROBS)
        now = datetime.now(timezone.utc)
        return [
            RollRecord(
                server_seed="",
                client_seed="",
                nonce=i,
                raw_output=b"",
                outcome=int(outcomes[i]),
                timestamp=now,
                mechanism_id=self.MECHANISM_ID,
            )
            for i in range(quantity)
        ]

    # ============================= Verification =============================

    def verify(self, record: RollRecord) -> VerificationResult:
        raise NotImplementedError("Verification not needed for biased mechanism demo")