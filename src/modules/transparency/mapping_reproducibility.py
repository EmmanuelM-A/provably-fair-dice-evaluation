from typing import Callable, List

from src.modules.data import BinaryResult
from src.utils.types import RollRecord


def outcome_mapping_reproducibility(
    rolls: List[RollRecord],
    mapping_fn: Callable[[bytes], float],
    min_records: int = 100,
) -> BinaryResult:
    """
    Applies mapping_fn to each record's stored raw_output bytes and checks
    that the result matches the stored outcome. Tests only the output-to-outcome
    mapping step in isolation, independently of how raw_output was produced.

    A pass here combined with a determinism test failure indicates the HMAC
    generation chain is broken. A fail here combined with a determinism test
    pass indicates the mapping function is not independently reproducible from
    the publicly disclosed specification.
    """
    if len(rolls) < min_records:
        raise ValueError(
            f"Outcome mapping reproducibility requires at least {min_records} records. "
            f"Got {len(rolls)}."
        )

    mismatches: List[int] = []
    mapping_errors: List[int] = []
    for i, record in enumerate(rolls):
        try:
            recomputed = mapping_fn(record.raw_output)
        except Exception:
            mapping_errors.append(i)
            continue
        if recomputed != record.outcome:
            mismatches.append(i)

    passed = len(mismatches) == 0 and len(mapping_errors) == 0
    if passed:
        message = (
            f"All {len(rolls)} records reproduced via the mapping function — "
            "outcome mapping is independently reproducible."
        )
    else:
        parts = []
        if mismatches:
            parts.append(f"{len(mismatches)} outcome mismatch(es)")
        if mapping_errors:
            parts.append(f"{len(mapping_errors)} mapping error(s)")
        message = "; ".join(parts) + " detected."

    return BinaryResult(
        test_name="outcome_mapping_reproducibility",
        passed=passed,
        message=message,
        details={
            "n_records": len(rolls),
            "n_passed": len(rolls) - len(mismatches) - len(mapping_errors),
            "n_mismatches": len(mismatches),
            "n_mapping_errors": len(mapping_errors),
            "mismatch_indices": mismatches[:20],
        },
    )
