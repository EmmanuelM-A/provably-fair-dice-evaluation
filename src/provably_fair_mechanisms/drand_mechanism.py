"""
Generates N roll records using drand beacon randomness and writes them to
a specified csv file.
"""

import argparse
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from typing import List

from src.enigines.randomness import RandomnessEngine
from src.enigines.verification import VerificationEngine
from src.logger.base_logger import BaseLogger
from src.utils.types import RollRecord, VerificationResult


class DrandMechanism(RandomnessEngine, VerificationEngine):

    # ========================= MECHANISM SPECIFIC =========================
    
    def __init__(self) -> None:
        self._CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
        self._ENDPOINTS = [
            "https://drand.cloudflare.com",
            "https://api.drand.sh",
        ]
        self.MECHANISM_ID = "drand-quicknet"
        self._logger = BaseLogger(__name__)
    
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
                self._logger.warning(f"Endpoint {endpoint} failed: {exc}, trying next...")

        raise ConnectionError(f"All drand endpoints failed for path: {path}")


    def fetch_chain_info(self) -> dict:
        """
        Retrieves metadata about the drand chain including the chain hash, public
        key, and beacon period in seconds.
        """
        return self._get_request("/info")


    def fetch_latest_beacon(self) -> dict:
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


    def fetch_beacon_by_round(self, round_number: int) -> dict:
        """
        Returns the beacon for a specific round number. Since drand beacons are
        permanent the same round always returns the same output.
        """
        return self._get_request(f"/public/{round_number}")

    # ======================== RANDOMNESS OPERATIONS ========================

    def generate_rolls(self, quantity: int, output_file: str) -> List[RollRecord]:
        # Fetch chain info once per session. The chain hash acts as the server_seed
        # for the entire session — it is the public identifier of the randomness
        # source and does not change between rolls.        
        self._logger.info("Fetching drand chain info...")
        chain_info = self.fetch_chain_info()

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
        latest_beacon = self.fetch_latest_beacon()
        start_round = latest_beacon["round"]
        self._logger.info(f"Starting from round {start_round}")

        # ======================== Roll generation ========================

        records = []

        for i in range(args.count):
            # Each roll uses the next sequential round number.
            # Sequential rounds ensure each roll has a unique, ordered nonce.
            target_round = start_round + i

            _logger.info(f"Roll {i + 1}/{args.count} — fetching round {target_round}...")

            # If the target round is in the future, wait for it to be published.
            # drand publishes a new beacon every `period_seconds` seconds.
            # We poll until the round is available.
            beacon = None
            while beacon is None:
                try:
                    beacon = fetch_beacon_by_round(target_round)
                except requests.HTTPError as exc:
                    if exc.response.status_code in (404, 425):
                        # Round not published yet (404 = not found, 425 = too early).
                        # Wait one period and retry.
                        _logger.debug(
                            f"Round {target_round} not yet available, "
                            f"waiting {period_seconds}s..."
                        )
                        time.sleep(period_seconds)
                    else:
                        raise

            # randomness is a 64-character hex string = 32 bytes.
            raw_output = bytes.fromhex(beacon["randomness"])

            # Derive the dice outcome from the raw bytes.
            outcome = rejection_sampling(
                raw_output=raw_output,
                rejection_threshold=REJECTION_THRESHOLD,
                max_value=MAX_VALUE,
            )

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
                    "timestamp": datetime.now(timezone.utc).strftime(DATE_FORMAT),
                    "mechanism_id": MECHANISM_ID,
                }
            )

            _logger.info(f"Round {target_round} -> outcome={outcome}")

        # ========================== Write output ==========================

        df = pd.DataFrame(records)

        # Ensure the output directory exists before writing.
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        df.to_csv(args.output, index=False)

        _logger.info(f"Done. {len(df)} rolls written to {args.output}")
        _logger.info(f"\n{df.head()}")

    # ======================= VERIFICATION OPERATIONS =======================

    def verify(
        self, record: RollRecord, disclosed_server_seed: str = ""
    ) -> VerificationResult:
        raise NotImplementedError()
