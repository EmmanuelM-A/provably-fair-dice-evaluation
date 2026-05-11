from src.enigines.randomness import RandomnessEngine
from src.enigines.verification import VerificationEngine
from src.utils.types import RollRecord, VerificationResult


class ChainlinkVRFMechanism(RandomnessEngine, VerificationEngine):

    # ========================= MECHANISM SPECIFIC =========================

    # ======================== RANDOMNESS OPERATIONS ========================

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

    # ======================= VERIFICATION OPERATIONS =======================

    def verify(
        self, record: RollRecord, disclosed_server_seed: str
    ) -> VerificationResult:
        pass
