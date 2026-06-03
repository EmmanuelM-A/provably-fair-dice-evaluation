import hashlib
import hmac
import math
import os
from datetime import datetime, timezone
from typing import List

import pandas as pd

from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.utils.types import RollRecord, VerificationResult

# Matches Stake's MAX_ROLL constant for their dice game.
_MAX_ROLL = 10001


def stake_dice_outcome(raw_output: bytes) -> float:
    """
    Module-level wrapper around StakesHMACMechanism._dice_outcome for use as a
    mapping_fn in the evaluation engine.
    """
    return StakesHMACMechanism._dice_outcome(raw_output)


class StakesHMACMechanism(ProvablyFairDiceMechanism):
    """
    Provably fair dice mechanism replicating Stake.com's publicly disclosed
    off-chain HMAC-SHA256 architecture.

    Algorithm (source: stake.com/provably-fair/implementation):
    1. Server seed: os.urandom(32).hex()  — 64-char hex string.
    2. Commitment:  SHA-256(server_seed)  — published before any bets.
    3. Per-roll:    HMAC-SHA256(key=server_seed, msg="{client_seed}:{nonce}:{cursor}")
       where cursor = 0 for single-outcome games.
    4. Outcome:     floor(bytes_to_number(digest[:4]) * MAX_ROLL) / 100
       giving a float in [0.00, 100.00] with two decimal places.
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
        return os.urandom(32).hex()

    @staticmethod
    def _commit(server_seed: str) -> str:
        return hashlib.sha256(server_seed.encode()).hexdigest()

    def _verify_commitment(self, server_seed: str, published_commitment: str) -> bool:
        recomputed_commitment = self._commit(server_seed)
        return self.safe_compare(recomputed_commitment, published_commitment)

    def _generate_raw_output(
        self, server_seed: str, client_seed: str, nonce: int, cursor: int = 0
    ) -> bytes:
        """
        HMAC-SHA256(key=server_seed, msg="{client_seed}:{nonce}:{cursor}")

        The cursor tracks the 32-byte chunk index for multi-outcome games.
        For a single dice roll only one 4-byte chunk is needed, so cursor = 0.
        """
        message = f"{client_seed}:{nonce}:{cursor}".encode()
        return hmac.new(
            server_seed.encode(),
            message,
            digestmod=hashlib.sha256,
        ).digest()

    @staticmethod
    def _bytes_to_number(digest: bytes) -> float:
        """
        Converts the first 4 bytes of an HMAC digest to a float in [0, 1).

        Matches Stake's bytes_to_number implementation:
            total = byte[0]/256 + byte[1]/256^2 + byte[2]/256^3 + byte[3]/256^4
        """
        total = 0.0
        for i in range(4):
            total += digest[i] / (256 ** (i + 1))
        return total

    @staticmethod
    def _dice_outcome(digest: bytes) -> float:
        """
        Maps an HMAC digest to a Stake-style dice result in [0.00, 100.00].

        Formula: floor(bytes_to_number(digest) * MAX_ROLL) / 100
        where MAX_ROLL = 10001, matching Stake's published dice implementation.
        """
        return math.floor(StakesHMACMechanism._bytes_to_number(digest) * _MAX_ROLL) / 100

    # ======================== RANDOMNESS OPERATIONS ========================

    def generate_rolls(
        self, quantity: int, save_rolls: bool = True
    ) -> List[RollRecord]:
        _SERVER_SEED_ROTATION = 70
        _CLIENT_SEED_ROTATIONS = 3
        client_rotation_every = quantity // (_CLIENT_SEED_ROTATIONS + 1)

        rolls: List[RollRecord] = []
        records = []

        server_seed = self._generate_server_seed()
        client_seed = self._client_seed
        session_nonce = 0

        commitment = self._commit(server_seed)
        self._logger.info(f"Commitment (SHA-256 of server seed): {commitment}")
        self._logger.info(f"Client seed: {client_seed}")

        for i in range(quantity):
            if client_rotation_every > 0 and i > 0 and i % client_rotation_every == 0:
                client_seed = os.urandom(16).hex()
                self._logger.info(f"Roll {i + 1}: client seed rotated -> {client_seed[:8]}...")

            if i > 0 and i % _SERVER_SEED_ROTATION == 0:
                server_seed = self._generate_server_seed()
                session_nonce = 0
                commitment = self._commit(server_seed)
                self._logger.info(
                    f"Roll {i + 1}: new session — server seed rotated, commitment: {commitment[:16]}..."
                )

            session_nonce += 1

            self._logger.info(f"Roll {i + 1}/{quantity} (session nonce {session_nonce})...")

            raw_output = self._generate_raw_output(
                server_seed=server_seed,
                client_seed=client_seed,
                nonce=session_nonce,
                cursor=0,
            )

            outcome = self._dice_outcome(raw_output)

            records.append(
                {
                    "server_seed": server_seed,
                    "client_seed": client_seed,
                    "nonce": session_nonce,
                    "raw_output": raw_output.hex(),
                    "outcome": outcome,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mechanism_id": self.MECHANISM_ID,
                }
            )

            rolls.append(
                RollRecord(
                    server_seed=server_seed,
                    client_seed=client_seed,
                    nonce=session_nonce,
                    raw_output=raw_output,
                    outcome=outcome,
                    timestamp=datetime.now(timezone.utc),
                    mechanism_id=self.MECHANISM_ID,
                )
            )

            self._logger.info(f"Nonce {session_nonce} -> outcome={outcome:.2f}")

        df = pd.DataFrame(records)

        if save_rolls:
            os.makedirs(os.path.dirname(self._output_file), exist_ok=True)
            df.to_csv(self._output_file, index=False)
            self._logger.info(f"Done. {len(df)} rolls written to {self._output_file}")
        else:
            self._logger.info(f"Done. {len(df)} rolls generated (not saved).")

        return rolls

    # ======================= VERIFICATION OPERATIONS =======================

    def verify(self, record: RollRecord) -> VerificationResult:
        """
        Recomputes the outcome from the disclosed server seed and confirms it
        matches the recorded outcome, replicating what a player would do
        post-session to verify fairness.
        """
        recomputed_output = self._generate_raw_output(
            server_seed=record.server_seed,
            client_seed=record.client_seed,
            nonce=record.nonce,
            cursor=0,
        )

        recomputed_outcome = self._dice_outcome(recomputed_output)

        # Format to two decimal places — matches Stake's .toFixed(2) output.
        recorded_str = f"{record.outcome:.2f}"
        recomputed_str = f"{recomputed_outcome:.2f}"

        is_match = self.safe_compare(recorded_str, recomputed_str)

        return VerificationResult(
            record=record,
            disclosed_server_seed=record.server_seed,
            recomputed_outcome=recomputed_outcome,
            match=is_match,
        )
