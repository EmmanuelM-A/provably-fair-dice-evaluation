"""
This module defines the ProvablyFairDiceMechanism interface, which serves as a
common base for all provably fair dice mechanisms implemented in this project.
It includes both randomness generation and verification capabilities, allowing
us to treat different mechanisms uniformly in our evaluation engine.
"""

from abc import ABC, abstractmethod
import hmac
from typing import List

from src.utils.types import RollRecord, VerificationResult


class ProvablyFairDiceMechanism(ABC):
    """
    Define a unified interface for provably fair dice mechanisms that includes
    both randomness generation and verification.
    """

    # ========================= Randomness Generation =========================

    @abstractmethod
    def generate_rolls(self, quantity: int, save_rolls: bool = True) -> List[RollRecord]:
        raise NotImplementedError()

    # ============================= Verification =============================

    @abstractmethod
    def verify(
        self, record: RollRecord, disclosed_server_seed: str = ""
    ) -> VerificationResult:
        raise NotImplementedError()
    
    @staticmethod
    def safe_compare(a: str, b: str) -> bool:
        """
        Compares two byte strings in such a way that is resistant to timing
        attacks.
        """
        return hmac.compare_digest(a, b)
