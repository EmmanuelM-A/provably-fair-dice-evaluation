import hashlib
import hmac

import os
from datetime import datetime, timezone
from typing import List

import pandas as pd

from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.utils.output_to_outcome_mapping import rejection_sampling
from src.utils.types import RollRecord, VerificationResult


class HMACMechanism(ProvablyFairDiceMechanism):
    """
    The concrete implementation of a traditional provably fair dice mechanism
    using HMAC (off-chain approach).
    """

    # ========================= MECHANISM SPECIFIC =========================

    def __init__(self, output_file: str) -> None:
        self._client_seed = "example-client-seed-12345"
        self.MECHANISM_ID = "hmac-sha256"
        self._output_file = output_file
        self._logger = BaseLogger(__name__)
    
    def __str__(self) -> str:
        return "HMAC-SHA256 Mechanism"

    @staticmethod
    def _generate_server_seed() -> str:
        """
        Generates a random server seed using the OS's cryptographically
        secure random number generator.
        """
        return os.urandom(32).hex()

    @staticmethod
    def _commit(server_seed: str) -> str:
        """
        Produces a server seed commitment which is published before the game
        round starts.
        """
        return hashlib.sha256(server_seed.encode()).hexdigest()

    def _verify_commitment(self, server_seed: str, published_commitment: str) -> bool:
        """
        Verifies that the disclosed server seed matches the published commitment.
        """
        recomputed_commitment = self._commit(server_seed)
        return self.safe_compare(recomputed_commitment, published_commitment)

    def _generate_raw_output(
        self, server_seed: str, client_seed: str, nonce: int
    ) -> bytes:
        """
        HMAC-SHA256(key=server_seed, msg=f"{client_seed}:{nonce}") produces
        32 bytes of pseudorandom data.
        """
        message = f"{client_seed}:{nonce}".encode()
        return hmac.new(
            server_seed.encode(),
            message,
            digestmod=hashlib.sha256,
        ).digest()

    # ======================== RANDOMNESS OPERATIONS ========================

    def generate_rolls(self, quantity: int, save_rolls: bool = True) -> List[RollRecord]:
        rolls: List[RollRecord] = []
        records = []

        server_seed = self._generate_server_seed()

        commitment = self._commit(server_seed)
        self._logger.info(f"Commitment (SHA-256 of server seed): {commitment}")
        self._logger.info(f"Client seed: {self._client_seed}")

        for i in range(quantity):
            nonce = i + 1

            self._logger.info(f"Roll {nonce}/{quantity}...")

            raw_output = self._generate_raw_output(self._client_seed, server_seed, nonce)

            # Map the raw bytes to a dice outcome using rejection sampling.
            outcome = rejection_sampling(raw_output=raw_output)

            records.append(
                {
                    # The server seed is stored in plaintext here because this is
                    # a post-session record. In a real system it would only be
                    # revealed after the session ends and the commitment is verified.
                    "server_seed": server_seed,
                    "client_seed": self._client_seed,
                    "nonce": nonce,
                    "raw_output": raw_output.hex(),
                    "outcome": outcome,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mechanism_id": self.MECHANISM_ID,
                }
            )

            rolls.append(
                RollRecord(
                    server_seed=server_seed,
                    client_seed=self._client_seed,
                    nonce=nonce,
                    raw_output=raw_output,
                    outcome=outcome,
                    timestamp=datetime.now(timezone.utc),
                    mechanism_id=self.MECHANISM_ID,
                )
            )

            self._logger.info(f"Nonce {nonce} -> outcome={outcome}")

        df = pd.DataFrame(records)

        if save_rolls:
            os.makedirs(os.path.dirname(self._output_file), exist_ok=True)
            df.to_csv(self._output_file, index=False)
            self._logger.info(f"Done. {len(df)} rolls written to {self._output_file}")
        else:
            self._logger.info(f"Done. {len(df)} rolls generated (not saved).")

        return rolls

    # ======================= VERIFICATION OPERATIONS =======================

    def verify(
        self, record: RollRecord, disclosed_server_seed: str = ""
    ) -> VerificationResult:
        """
        Independently recompute the outcome from a disclosed server seed and
        confirm it matches the recorded outcome. Replicating what a user
        would do post-game/match/session to verify fairness.
        """        
        recomputed_output = self._generate_raw_output(
            server_seed=disclosed_server_seed,
            client_seed=record.client_seed,
            nonce=record.nonce
        )

        recomputed_outcome = rejection_sampling(recomputed_output)

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
