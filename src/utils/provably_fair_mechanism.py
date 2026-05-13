"""
Utility interface to provide a whole provably fiar mechanism of which has all
the operations, both randomness and verification, are present to produce the
needed results, rather than having all implementations/mechanisms implement two
separate interfaces.
"""

from src.enigines.randomness import RandomnessEngine
from src.enigines.verification import VerificationEngine
from src.utils.types import RollRecord, VerificationResult


class ProvablyFairDiceMechanism(RandomnessEngine, VerificationEngine):
    """
    Utility interface to provide a whole provably fair mechanism interface.
    """

    def get_entropy(self) -> bytes:
        pass

    def get_noise(self) -> bytes:
        pass

    def get_drbg_instance(self) -> any:
        pass

    def generate_roll(
        self, server_seed: str, client_seed: str, nonce: str = ""
    ) -> RollRecord:
        pass

    def verify(
        self, record: RollRecord, disclosed_server_seed: str
    ) -> VerificationResult:
        pass