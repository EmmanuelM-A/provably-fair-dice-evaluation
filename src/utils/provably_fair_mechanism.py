"""
Utility interface to provide a whole provably fiar mechanism of which has all
the operations, both randomness and verification, are present to produce the
needed results, rather than having all implementations/mechanisms implement two
separate interfaces.
"""

from typing import List

from src.enigines.randomness import RandomnessEngine
from src.enigines.verification import VerificationEngine
from src.utils.types import RollRecord, VerificationResult


class ProvablyFairDiceMechanism(RandomnessEngine, VerificationEngine):
    """
    Utility interface to provide a whole provably fair mechanism interface.
    """

    def generate_rolls(self) -> List[RollRecord]:
        raise NotImplementedError()

    def verify(
        self, record: RollRecord, disclosed_server_seed: str = ""
    ) -> VerificationResult:
        raise NotImplementedError()
