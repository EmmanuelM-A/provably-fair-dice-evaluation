from collections import Counter
from typing import List

from src.modules.data import BinaryResult
from src.utils.types import RollRecord


def check_seed_reuse(records: List[RollRecord]) -> BinaryResult:
    """Measure how often the same seed value for both client and server are reused across rolls."""
    server_counts = Counter(r.server_seed for r in records)
    client_counts = Counter(r.client_seed for r in records)

    reused_server = {s: c for s, c in server_counts.items() if c > 1}
    reused_client = {s: c for s, c in client_counts.items() if c > 1}

    passed = len(reused_server) == 0 and len(reused_client) == 0
    if passed:
        message = f"No seed reuse detected across {len(records)} records."
    else:
        parts = []
        if reused_server:
            parts.append(f"{len(reused_server)} server seed(s) reused")
        if reused_client:
            parts.append(f"{len(reused_client)} client seed(s) reused")
        message = "; ".join(parts) + "."

    return BinaryResult(
        test_name="seed_reuse",
        passed=passed,
        message=message,
        details={
            "n_records": len(records),
            "n_reused_server_seeds": len(reused_server),
            "n_reused_client_seeds": len(reused_client),
        },
    )
