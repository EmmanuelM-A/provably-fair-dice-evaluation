from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from src.enigines.pfd import ProvablyFairDiceMechanism
from src.modules.data import BinaryResult
from src.utils.types import RollRecord


def determinism_test(
    rolls: List[RollRecord],
    mechanism: ProvablyFairDiceMechanism,
    min_records: int = 100,
) -> BinaryResult:
    """
    For each record, re-derives the raw output from (server_seed, client_seed,
    nonce) via mechanism.verify() and confirms the recomputed outcome matches
    the stored outcome. Tests the full generation chain end-to-end.

    The server_seed in each RollRecord is treated as the disclosed seed — in
    a real deployment this would only be available post-session reveal.
    """
    if len(rolls) < min_records:
        raise ValueError(
            f"Determinism test requires at least {min_records} records. Got {len(rolls)}."
        )

    mismatches: List[int] = []
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(mechanism.verify, record): i for i, record in enumerate(rolls)}
        for future in as_completed(futures):
            i = futures[future]
            result = future.result()
            if not result.match:
                mismatches.append(i)
    mismatches.sort()

    passed = len(mismatches) == 0
    message = (
        f"All {len(rolls)} records reproduced correctly — mechanism is deterministic."
        if passed
        else (
            f"{len(mismatches)} of {len(rolls)} record(s) failed to reproduce. "
            "Disclosure integrity failure — further investigation required."
        )
    )
    return BinaryResult(
        test_name="determinism",
        passed=passed,
        message=message,
        details={
            "n_records": len(rolls),
            "n_passed": len(rolls) - len(mismatches),
            "n_mismatches": len(mismatches),
            "mismatch_indices": mismatches[:20],
        },
    )
