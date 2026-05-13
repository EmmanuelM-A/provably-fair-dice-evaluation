import hashlib
import hmac

import os
from datetime import datetime, timezone

from src.config.configs import MAX_VALUE, REJECTION_THRESHOLD
from src.enigines.randomness import RandomnessEngine
from src.enigines.verification import VerificationEngine
from src.utils.output_to_outcome_mapping import rejection_sampling
from src.utils.types import RollRecord, VerificationResult


class ProvablyFairDiceHMACMechanism(RandomnessEngine, VerificationEngine):
    """
    The concrete implementation of a traditional provably fair dice mechanism
    using HMAC (off-chain approach).
    """

    # ========================= MECHANISM SPECIFIC =========================

    def __init__(self) -> None:
        self._MAX_UNIT32 = 2**32
        self._MAX_VALUE = 10_000  # [0, MAX_VALUE] -> MAX_VALUE possible outcomes
        self._REJECTION_THRESHOLD = (
            self._MAX_UNIT32 // self._MAX_VALUE
        ) * self._MAX_VALUE
        self._BYTES_PER_CHUNK = 4
        self._CHUNKS_PER_DIGEST = 32 // self._BYTES_PER_CHUNK
        self.MECHANISM_ID = "hmac-sha256"

    @staticmethod
    def commit(server_seed: str) -> str:
        """
        Produces a server seed commitment which is published before the game
        round starts.
        """
        return hashlib.sha256(server_seed.encode()).hexdigest()

    def verify_commitment(self, server_seed: str, published_commitment: str) -> bool:
        """
        Verifies that the disclosed server seed matches the published commitment.
        """
        recomputed_commitment = self.commit(server_seed)
        return self.safe_compare(recomputed_commitment, published_commitment)

    # ======================== RANDOMNESS OPERATIONS ========================

    def get_entropy(self) -> bytes:
        """
        os.urandom() returns a random byte string of the specified length
        suitable for use in HMAC. It draws it from /dev/urandom on Linux/macOS
        and CryptGenRandom on Windows, which are both designed to be
        cryptographically secure.
        """
        return os.urandom(32)

    def get_noise(self) -> bytes:
        """
        Not applicable for the HMAC commit-reveal mechanism.

        The HMAC construction derives all randomness from the server seed,
        client seed, and nonce. No additional noise input is used.
        """
        return b""

    def get_drbg_instance(self) -> None:
        """
        Not applicable for the HMAC commit-reveal mechanism.

        HMAC-SHA256 is used directly as the randomness function. There is
        no separate DRBG instance to configure or manage.
        """
        return None

    def generate_roll(
        self, server_seed: str, client_seed: str, nonce: str = ""
    ) -> RollRecord:
        """
        Generates a single provably fair dice outcome.

        Process:
        - Compute ``HMAC-SHA256(...)`` to produce 32 bytes of pseudorandom data.
        HMAC is used instead of plain SHA-256 to prevent length-extension
        attacks (NIST FIPS 198-1).
        - Iterate over the digest in 4-byte chunks, applying rejection sampling
        to eliminate modulo bias, to produce the outcome.
        """

        # The same message format used by platforms like Stake, Primedice and
        # Bustabit
        message = f"{client_seed}:{nonce}".encode()

        raw_output = hmac.new(
            server_seed.encode(), message, digestmod=hashlib.sha256
        ).digest()

        outcome = rejection_sampling(
            raw_output=raw_output,
            rejection_threshold=REJECTION_THRESHOLD,
            max_value=MAX_VALUE,
        )

        return RollRecord(
            server_seed=server_seed,
            client_seed=client_seed,
            nonce=nonce,
            raw_output=raw_output,
            outcome=outcome,
            timestamp=datetime.now(timezone.utc),
            mechanism_id=self.MECHANISM_ID,
        )

    # ======================= VERIFICATION OPERATIONS =======================

    def verify(
        self, record: RollRecord, disclosed_server_seed: str
    ) -> VerificationResult:
        """
        Independently recompute the outcome from a disclosed server seed and
        confirm it matches the recorded outcome. Replicating what a user
        would do post-game/match/session to verify fairness.
        """

        message = f"{record.client_seed}:{record.nonce}".encode()

        recomputed_output = hmac.new(
            disclosed_server_seed.encode(), message, digestmod=hashlib.sha256
        ).digest()

        recomputed_outcome = self._rejection_sampling(recomputed_output)

        # Formatted both outcomes to zero-padded 4-digit strs to ensure the
        # same length regardless of outcome values
        recorded_outcome_fl = f"{record.outcome:04d}"
        recomputed_outcome_fl = f"{recomputed_outcome:04d}"

        is_match = self.safe_compare(recomputed_outcome_fl, recorded_outcome_fl)

        return VerificationResult(
            record=record,
            disclosed_server_seed=disclosed_server_seed,
            recomputed_outcome=recomputed_outcome,
            match=is_match,
        )
