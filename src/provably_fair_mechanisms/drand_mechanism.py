"""
Generates N roll records using drand beacon randomness and writes them to
a specified csv file.
"""

import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from typing import List

from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.utils.output_to_outcome_mapping import rejection_sampling
from src.utils.types import RollRecord, VerificationResult


class DrandMechanism(ProvablyFairDiceMechanism):

    # ========================= MECHANISM SPECIFIC =========================

    def __init__(self, output_file: str) -> None:
        self._CHAIN_HASH = (
            "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
        )
        self._ENDPOINTS = [
            "https://drand.cloudflare.com",
            "https://api.drand.sh",
        ]
        self._output_file = output_file
        self.MECHANISM_ID = "drand-quicknet"
        self._logger = BaseLogger(__name__)
    
    def __str__(self) -> str:
        return "Drand Quicknet Mechanism"

    def _get_request(self, path: str) -> dict:
        """
        Helper to make GET requests to the drand API with endpoint failover.
        """
        for endpoint in self._ENDPOINTS:
            url = f"{endpoint}/{self._CHAIN_HASH}{path}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError:
                # HTTP errors (4xx/5xx) mean the server responded, both endpoints
                # will return the same status for a missing/future round, so don't
                # fall back; let the caller handle it.
                raise
            except requests.RequestException as exc:
                # Network-level failure (timeout, connection refused, etc.)
                # worth trying the next endpoint.
                self._logger.warning(
                    f"Endpoint {endpoint} failed: {exc}, trying next..."
                )

        raise ConnectionError(f"All drand endpoints failed for path: {path}")

    def _fetch_chain_info(self) -> dict:
        """
        Retrieves metadata about the drand chain including the chain hash, public
        key, and beacon period in seconds.
        """
        return self._get_request("/info")

    def _fetch_latest_beacon(self) -> dict:
        """
        Retrieves the most recently published beacon from the drand chain. In this
        format:
        {
            "round": 1234567,
            "randomness": "a3f8c2...", <- 64 hex chars = 32 bytes
            "signature": "b1d4e9..."
        }
        """
        return self._get_request("/public/latest")

    def _fetch_beacon_by_round(self, round_number: int) -> dict:
        """
        Returns the beacon for a specific round number. Since drand beacons are
        permanent the same round always returns the same output.
        """
        return self._get_request(f"/public/{round_number}")

    # ======================== RANDOMNESS OPERATIONS ========================

    def generate_rolls(self, quantity: int, save_rolls: bool = True) -> List[RollRecord]:
        # Fetch chain info once per session. The chain hash acts as the server_seed
        # for the entire session — it is the public identifier of the randomness
        # source and does not change between rolls.
        self._logger.info("Fetching drand chain info...")
        chain_info = self._fetch_chain_info()

        # server_seed is set once per session, not per roll.
        # This reflects how drand works: the chain hash is fixed and public.
        # It plays the role of the server seed commitment — it identifies the
        # source without revealing individual beacon outputs in advance.
        server_seed = chain_info["hash"]
        period_seconds = chain_info["period"]
        self._logger.info(f"Chain hash (server_seed): {server_seed}")
        self._logger.info(f"Beacon period: {period_seconds}s")

        # Fetch the latest beacon to find the current round number.
        # All subsequent rolls use rounds starting from here.
        self._logger.info("Fetching latest beacon to determine starting round...")
        latest_beacon = self._fetch_latest_beacon()
        start_round = latest_beacon["round"]
        self._logger.info(f"Starting from round {start_round}")

        # ======================== Roll generation ========================

        rolls: List[RollRecord] = []
        records = []

        for i in range(quantity):
            # Each roll uses the next sequential round number.
            # Sequential rounds ensure each roll has a unique, ordered nonce.
            target_round = start_round + i

            self._logger.debug(
                f"Roll {i + 1}/{quantity} — fetching round {target_round}..."
            )

            # If the target round is in the future, wait for it to be published.
            # drand publishes a new beacon every `period_seconds` seconds.
            # We poll until the round is available.
            beacon = None
            while beacon is None:
                try:
                    beacon = self._fetch_beacon_by_round(target_round)
                except requests.HTTPError as exc:
                    if exc.response.status_code in (404, 425):
                        # Round not published yet (404 = not found, 425 = too early).
                        # Wait one period and retry.
                        self._logger.debug(
                            f"Round {target_round} not yet available, "
                            f"waiting {period_seconds}s..."
                        )
                        time.sleep(period_seconds)
                    else:
                        raise

            # randomness is a 64-character hex string = 32 bytes.
            raw_output = bytes.fromhex(beacon["randomness"])

            # Derive the dice outcome from the raw bytes.
            outcome = rejection_sampling(raw_output=raw_output)

            records.append(
                {
                    # server_seed is the chain hash set once at session start.
                    "server_seed": server_seed,
                    # client_seed is empty, neither the player nor the platform
                    # supplies any input to drand. This is architecturally significant.
                    "client_seed": "",
                    # nonce is the round number, drand's monotonically incrementing
                    # counter that uniquely identifies each beacon.
                    "nonce": target_round,
                    # raw_output stored as hex so it survives serialisation round-trips.
                    "raw_output": raw_output.hex(),
                    "outcome": outcome,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mechanism_id": self.MECHANISM_ID,
                }
            )
            
            rolls.append(
                RollRecord(
                    server_seed=server_seed,
                    client_seed="",
                    nonce=target_round,
                    raw_output=raw_output,
                    outcome=outcome,
                    timestamp=datetime.now(timezone.utc),
                    mechanism_id=self.MECHANISM_ID,
                )
            )

            self._logger.debug(f"Round {target_round} -> outcome={outcome}")

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
        recomputed_outcome = -1
        is_match = False

        try:
            # record.nonce holds the round number written during generate_roll.
            # Fetching by round number gives us the exact beacon that was used.
            beacon = self._get_request(f"/public/{record.nonce}")

            check_1 = self._check_randomness_matches(beacon, record)
            check_2 = self._check_chain_integrity(beacon, record)

            if check_1 and check_2:
                # Recompute the outcome from the stored raw bytes and compare.
                recomputed_outcome = rejection_sampling(raw_output=record.raw_output)
                is_match = recomputed_outcome == record.outcome

        except Exception as exc:
            self._logger.error(f"Verification failed for round={record.nonce}: {exc}")

        return VerificationResult(
            record=record,
            disclosed_server_seed=self._CHAIN_HASH,
            recomputed_outcome=recomputed_outcome,
            match=is_match,
        )

    def _check_randomness_matches(self, beacon: dict, record: RollRecord) -> bool:
        # Decode the on-chain randomness for this round and compare it to what
        # was stored in the record during generation. drand beacons are
        # deterministic and permanent — the same round always returns the same
        # randomness. Any mismatch means the record was tampered with.
        on_chain_randomness = bytes.fromhex(beacon["randomness"])
        result = on_chain_randomness == record.raw_output

        if not result:
            self._logger.warning(
                f"Check 1 failed: on-chain randomness does not match "
                f"recorded raw_output for round={record.nonce}"
            )
        return result

    def _check_chain_integrity(self, beacon: dict, record: RollRecord) -> bool:
        """
        Each beacon is chained to the one before it. The current beacon
        contains a signature field. The previous beacon's signature should
        match the current beacon's previous_signature field.
        
        We fetch round N-1 and confirm:
        - beacon[N]["previous_signature"] == beacon[N-1]["signature"]
        
        This proves the beacon at round N was produced as part of the
        legitimate chain and not inserted out of nowhere.
        """
        
        if record.nonce <= 1:
            # Round 1 has no previous beacon to check against.
            self._logger.debug("Chain integrity check skipped for round 1.")
            return True

        prior_beacon = self._get_request(f"/public/{record.nonce - 1}")

        current_prev_sig = beacon.get("previous_signature", "")
        prior_sig = prior_beacon.get("signature", "")

        if not current_prev_sig or not prior_sig:
            self._logger.debug(
                f"Chain integrity check skipped for round={record.nonce}: "
                "unchained mode detected (no previous_signature field)."
            )
            return True

        result = current_prev_sig == prior_sig

        if not result:
            self._logger.warning(
                f"Check 2 failed: chain integrity broken at round={record.nonce}. "
                f"previous_signature does not match prior round signature."
            )
        return result
