"""
Generates provably fair dice rolls using drand quicknet randomness, modelling
BlockRand's three-input commit-reveal protocol.

Implementation source: BlockRand (https://blockrand.io)
Algorithm:
    1. Server generates server_secret = os.urandom(32).hex() and publishes
        SHA256(server_secret) as a commitment before the game.
    2. Player supplies player_secret (client_seed).
    3. A future drand round is agreed upon; once published, its BLS threshold
        signature is used as the on-chain randomness input.
    4. Final seed: SHA256(player_secret:server_secret:drand_signature).
    5. Outcome: rejection sampling on the seed bytes -> integer in [1, 100].
    6. Verification: re-fetch the drand signature for the stored round, recompute
        SHA256, apply rejection sampling, compare to stored outcome.

The drand quicknet chain (unchained BLS12-381 G1) is used; beacons are
published every 3 seconds and are permanently retrievable by round number.
"""

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List

import pandas as pd
import requests

from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.utils.common_operations import rejection_sampling
from src.utils.types import RollRecord, VerificationResult


def blockrand_dice_outcome(raw_output: bytes) -> float:
    """
    Module-level wrapper for use as mapping_fn in the evaluation engine.
    raw_output = SHA256(player_secret:server_secret:drand_signature).
    Maps to a dice outcome in [1, 100] via rejection sampling.
    """
    return float(rejection_sampling(raw_output))


class BlockRandDrandMechanism(ProvablyFairDiceMechanism):
    """
    Provably fair dice mechanism replicating BlockRand's drand-based
    commit-reveal protocol.
    """
    # ========================= MECHANISM SPECIFIC =========================

    _CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
    _ENDPOINTS = [
        "https://drand.cloudflare.com",
        "https://api.drand.sh",
    ]

    def __init__(self, output_file: str) -> None:
        self._player_secret = "example-player-secret-12345"
        self._output_file = output_file
        self.MECHANISM_ID = "blockrand-drand-quicknet"
        self._logger = BaseLogger(__name__)

    def __str__(self) -> str:
        return "BlockRand Drand Quicknet Mechanism"

    @staticmethod
    def _commit(server_secret: str) -> str:
        """SHA256(server_secret) — published as the pre-game commitment."""
        return hashlib.sha256(server_secret.encode()).hexdigest()

    def _verify_commitment(self, server_secret: str, published_commitment: str) -> bool:
        return self.safe_compare(self._commit(server_secret), published_commitment)

    def _get_request(self, path: str) -> dict:
        for endpoint in self._ENDPOINTS:
            url = f"{endpoint}/{self._CHAIN_HASH}{path}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError:
                # HTTP errors mean both endpoints will return the same status
                # (e.g. 404 for a future round), so don't fall back.
                raise
            except requests.RequestException as exc:
                self._logger.warning(
                    f"Endpoint {endpoint} failed: {exc}, trying next..."
                )

        raise ConnectionError(f"All drand endpoints failed for path: {path}")

    def _fetch_chain_info(self) -> dict:
        return self._get_request("/info")

    def _fetch_latest_beacon(self) -> dict:
        return self._get_request("/public/latest")

    def _fetch_beacon_by_round(self, round_number: int) -> dict:
        return self._get_request(f"/public/{round_number}")

    @staticmethod
    def _derive_raw_output(
        player_secret: str, server_secret: str, drand_signature: str
    ) -> bytes:
        """
        BlockRand seed derivation:
        SHA256(player_secret:server_secret:drand_signature)
        """
        seed_input = f"{player_secret}:{server_secret}:{drand_signature}".encode()
        return hashlib.sha256(seed_input).digest()

    # ======================== RANDOMNESS OPERATIONS ========================

    def generate_rolls(
        self, quantity: int, save_rolls: bool = True
    ) -> List[RollRecord]:
        _SERVER_SEED_ROTATION = 190
        _CLIENT_SEED_ROTATIONS = 3
        client_rotation_every = quantity // (_CLIENT_SEED_ROTATIONS + 1)

        # 1. Generate a fresh server_secret and publish its pre-game commitment.
        server_secret = os.urandom(32).hex()
        player_secret = self._player_secret
        commitment = self._commit(server_secret)
        self._logger.info(f"Server commitment (SHA256 of server_secret): {commitment}")
        self._logger.info(f"Player secret: {player_secret}")

        # 2. Find the starting drand round.
        self._logger.info("Fetching latest drand beacon to determine starting round...")
        latest_beacon = self._fetch_latest_beacon()
        chain_info = self._fetch_chain_info()
        period_seconds = chain_info["period"]
        # Start from a past round so all beacons are already published —
        # no per-roll waiting required.
        start_round = max(1, latest_beacon["round"] - quantity + 1)
        self._logger.info(f"Latest round={latest_beacon['round']}, starting from round {start_round} (historical)")

        rolls: List[RollRecord] = []
        records = []

        # 3. Pre-fetch all beacon rounds concurrently before the processing loop.
        all_rounds = list(range(start_round, start_round + quantity))
        beacons: dict[int, dict] = {}

        def _fetch_round(round_number: int) -> tuple:
            beacon = None
            while beacon is None:
                try:
                    beacon = self._fetch_beacon_by_round(round_number)
                except requests.HTTPError as exc:
                    if exc.response.status_code in (404, 425):
                        self._logger.debug(
                            f"Round {round_number} not yet available, "
                            f"waiting {period_seconds}s..."
                        )
                        time.sleep(period_seconds)
                    else:
                        raise
            return round_number, beacon

        self._logger.info(f"Pre-fetching {quantity} drand beacons concurrently...")
        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = {executor.submit(_fetch_round, r): r for r in all_rounds}
            for future in as_completed(futures):
                round_number, beacon = future.result()
                beacons[round_number] = beacon
        self._logger.info("Beacon pre-fetch complete.")

        for i in range(quantity):
            # Rotate player_secret (client seed) — nonce continues unaffected.
            if client_rotation_every > 0 and i > 0 and i % client_rotation_every == 0:
                player_secret = os.urandom(16).hex()
                self._logger.info(f"Roll {i + 1}: player secret rotated -> {player_secret[:8]}...")

            # Rotate server_secret — nonce (drand round) is external, never resets.
            if i > 0 and i % _SERVER_SEED_ROTATION == 0:
                server_secret = os.urandom(32).hex()
                commitment = self._commit(server_secret)
                self._logger.info(
                    f"Roll {i + 1}: server secret rotated, commitment: {commitment[:16]}..."
                )

            target_round = start_round + i

            self._logger.debug(
                f"Roll {i + 1}/{quantity} — round {target_round}..."
            )

            # 4. Derive the final seed from all three inputs.
            drand_signature = beacons[target_round]["signature"]
            raw_output = self._derive_raw_output(player_secret, server_secret, drand_signature)

            # 5. Map to a dice outcome via rejection sampling.
            outcome = float(rejection_sampling(raw_output=raw_output))

            self._logger.debug(
                f"Round {target_round} -> signature={drand_signature[:16]}..., outcome={outcome:.0f}"
            )

            records.append(
                {
                    "server_seed": server_secret,
                    "client_seed": player_secret,
                    "nonce": target_round,
                    "raw_output": raw_output.hex(),
                    "outcome": outcome,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mechanism_id": self.MECHANISM_ID,
                }
            )

            rolls.append(
                RollRecord(
                    server_seed=server_secret,
                    client_seed=player_secret,
                    nonce=target_round,
                    raw_output=raw_output,
                    outcome=outcome,
                    timestamp=datetime.now(timezone.utc),
                    mechanism_id=self.MECHANISM_ID,
                )
            )

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
        Re-fetches the drand beacon signature for the stored round (nonce),
        recomputes SHA256(player_secret:server_secret:drand_signature), applies
        rejection sampling, and compares to the stored outcome. Replicates what
        a player would do post-game on BlockRand to verify fairness.
        """
        recomputed_outcome: float = -1.0
        is_match = False

        try:
            beacon = self._fetch_beacon_by_round(record.nonce)
            drand_signature = beacon["signature"]

            recomputed_raw = self._derive_raw_output(
                player_secret=record.client_seed,
                server_secret=record.server_seed,
                drand_signature=drand_signature,
            )
            recomputed_outcome = float(rejection_sampling(raw_output=recomputed_raw))
            is_match = recomputed_outcome == record.outcome

        except Exception as exc:
            self._logger.error(f"Verification failed for round={record.nonce}: {exc}")

        return VerificationResult(
            record=record,
            disclosed_server_seed=record.server_seed,
            recomputed_outcome=recomputed_outcome,
            match=is_match,
        )
