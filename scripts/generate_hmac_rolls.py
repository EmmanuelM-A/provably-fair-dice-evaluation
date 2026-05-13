"""
Generates N roll records using a traditional HMAC-SHA256 commit-reveal
mechanism and writes them to a specified CSV file.
"""

import argparse
import hashlib
import hmac
import os
from datetime import datetime, timezone

import pandas as pd

from src.config.configs import REJECTION_THRESHOLD, MAX_VALUE, DATE_FORMAT
from src.logger.base_logger import BaseLogger
from src.utils.output_to_outcome_mapping import rejection_sampling

_logger = BaseLogger(__name__)

# =========================== HMAC helpers ===========================


def generate_server_seed() -> str:
    # os.urandom(32) draws 32 bytes from the OS CSPRNG (/dev/urandom on
    # Linux/macOS, CryptGenRandom on Windows). Converting to hex gives a
    # 64-character string suitable for use as a seed.
    return os.urandom(32).hex()


def commit(server_seed: str) -> str:
    # SHA-256(server_seed) is the commitment published before play begins.
    # The player stores this and verifies it after the server seed is revealed.
    return hashlib.sha256(server_seed.encode()).hexdigest()


def generate_raw_output(server_seed: str, client_seed: str, nonce: int) -> bytes:
    # HMAC-SHA256(key=server_seed, msg=f"{client_seed}:{nonce}") produces
    # 32 bytes of pseudorandom data.
    #
    # The message format "{client_seed}:{nonce}" uses a colon separator to
    # prevent collisions between different (client_seed, nonce) pairs that
    # would produce the same message without it. For example, without the
    # separator, client_seed="abc" nonce="1" and client_seed="ab" nonce="c1"
    # would be identical messages.
    message = f"{client_seed}:{nonce}".encode()
    return hmac.new(
        server_seed.encode(),
        message,
        digestmod=hashlib.sha256,
    ).digest()


# ================================== Main ==================================

"""
The dice rolls are generated via a traditional HMAC commit-reveal system,
to simulate how a developer/user would interact with this framework. In
reality you would simulate/interact with your own real PFD mechanism/system
or your actual game/application to generate or obtain the dice rolls.

For the purpose of this demo, the dice rolls generated are from a fictional
PFD mechanism used to generate provably fair dice rolls for a Backgammon game.

The seeds used for this fictional game are as such:
- The server_seed is generated fresh per-roll using os.urandom(32).
- The client_seed is a fixed string representing the player's chosen seed.
- The nonce starts at 1 and increments by 1 per roll.

Usage:
    python -m scripts.generate_hmac_rolls --count 100
"""

DEFAULT_OUTPUT = "data/rolls/hmac_rolls.csv"
MECHANISM_ID = "hmac-sha256"


def main():
    # ============================ ARGUMENTS ============================

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of roll records to generate.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT,
        help="Output file path. Use .csv extension.",
    )
    parser.add_argument(
        "--client-seed",
        type=str,
        default="player-client-seed",
        help="The client seed to use for all rolls in this session.",
    )
    args = parser.parse_args()

    # ========================= Session setup =========================

    # Generate a fresh server seed for this session.
    # In a real platform this would be generated server-side and kept secret
    # until the session ends.
    server_seed = generate_server_seed()
    _logger.info(f"Server seed generated (keep secret until session ends).")

    # Publish the commitment before any rolls are generated.
    # In a real platform this is shown to the player before they bet.
    commitment = commit(server_seed)
    _logger.info(f"Commitment (SHA-256 of server seed): {commitment}")
    _logger.info(f"Client seed: {args.client_seed}")

    # ======================== Roll generation ========================

    records = []

    for i in range(args.count):
        # Nonce starts at 1 and increments per roll.
        # This ensures every roll produces a unique raw_output even when
        # server_seed and client_seed remain the same across the session.
        nonce = i + 1

        _logger.info(f"Roll {nonce}/{args.count}...")

        # Compute HMAC-SHA256(server_seed, f"{client_seed}:{nonce}").
        raw_output = generate_raw_output(args.client_seed, server_seed, nonce)

        # Map the raw bytes to a dice outcome using rejection sampling.
        outcome = rejection_sampling(
            raw_output=raw_output,
            rejection_threshold=REJECTION_THRESHOLD,
            max_value=MAX_VALUE,
        )

        records.append(
            {
                # The server seed is stored in plaintext here because this is
                # a post-session record. In a real system it would only be
                # revealed after the session ends and the commitment is verified.
                "server_seed": server_seed,
                "client_seed": args.client_seed,
                "nonce": nonce,
                "raw_output": raw_output.hex(),
                "outcome": outcome,
                "timestamp": datetime.now(timezone.utc).strftime(DATE_FORMAT),
                "mechanism_id": MECHANISM_ID,
            }
        )

        _logger.info(f"Nonce {nonce} -> outcome={outcome}")

    # ========================== Write output ==========================

    df = pd.DataFrame(records)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)

    _logger.info(f"Done. {len(df)} rolls written to {args.output}")

    _logger.info(f"Session ended. Revealed server seed: {server_seed}")
    _logger.info(f"Verify by recomputing: SHA-256({server_seed}) == {commitment}")
    _logger.info(f"\n{df.head()}")


if __name__ == "__main__":
    main()