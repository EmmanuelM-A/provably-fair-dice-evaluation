import math
from collections import Counter
from typing import List

from src.modules.data import BinaryResult
from src.utils.types import RollRecord


def check_nonce_presence(records: List[RollRecord]) -> BinaryResult:
    """Check that all records carry a non-zero nonce."""
    missing = [i for i, r in enumerate(records) if r.nonce == 0]
    passed = len(missing) == 0
    message = (
        f"All {len(records)} records have a non-zero nonce."
        if passed
        else f"{len(missing)} record(s) have a zero or missing nonce."
    )
    return BinaryResult(
        test_name="nonce_presence",
        passed=passed,
        message=message,
        details={"n_records": len(records), "n_missing": len(missing)},
    )


def check_nonce_unpredictability(records: List[RollRecord]) -> float:
    """Use min-entropy to assess unpredictability of the nonce values."""
    nonces = [r.nonce for r in records]
    counts = Counter(nonces)
    max_prob = max(counts.values()) / len(nonces)
    return -math.log2(max_prob)


def check_nonce_uniqueness(records: List[RollRecord]) -> BinaryResult:
    """Check that (server_seed, nonce) pairs are unique across rolls.

    Bare nonce integers are legitimately reused when a server seed rotates —
    the HMAC key changes, so the outputs remain distinct. What must be unique
    is the (key, nonce) pair, not the nonce alone.
    """
    pairs = [(r.server_seed, r.nonce) for r in records]
    counts = Counter(pairs)
    duplicates = {p: c for p, c in counts.items() if c > 1}
    n_duplicate_rolls = sum(c - 1 for c in duplicates.values())
    passed = len(duplicates) == 0
    message = (
        f"All {len(records)} (server_seed, nonce) pairs are unique."
        if passed
        else f"{len(duplicates)} (server_seed, nonce) pair(s) reused ({n_duplicate_rolls} duplicate roll(s))."
    )
    return BinaryResult(
        test_name="nonce_uniqueness",
        passed=passed,
        message=message,
        details={
            "n_records": len(records),
            "n_duplicate_pairs": len(duplicates),
            "n_duplicate_rolls": n_duplicate_rolls,
        },
    )
