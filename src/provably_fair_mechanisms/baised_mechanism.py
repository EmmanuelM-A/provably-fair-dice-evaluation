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
    
    You can either use this implementation or modify it to create your own biased mechanism for testing purposes.
    """

    MECHANISM_ID = "biased"

    def __init__(self, config: EvaluationConfig) -> None:
        self._rng = np.random.default_rng()  # Ensure variability across runs
        self.config = config
        n = config.n_faces
        high = 1.0 / 3.0
        low = (1.0 - high) / (n - 1)
        self._BIASED_PROBS: list[float] = [low] * (n - 1) + [high]
        self._faces = np.arange(1, n + 1)

    # ========================= Randomness Generation =========================

    def generate_rolls(
        self, quantity: int, save_rolls: bool = True
    ) -> List[RollRecord]:
        outcomes = self._rng.choice(self._faces, size=quantity, p=self._BIASED_PROBS)
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