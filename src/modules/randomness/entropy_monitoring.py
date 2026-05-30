"""
Runtime entropy monitoring and entropy source validation.

Implements three checks:
- check_server_seed_min_entropy: One-time validation of the entropy source
  against the NIST SP 800-90B minimum min-entropy threshold (Section 3).
- repetition_count_test: Detects consecutive repeated values (Section 4.4.1).
- adaptive_proportion_test: Detects over-representation within a sliding
  window (Section 4.4.2).

The runtime monitoring tests scan the entire sample sequence and record every
position where an alarm fires, so degradation at any point is captured.

Reference: Turan et al., "Recommendation for the Entropy Sources Used for
Random Bit Generation", NIST SP 800-90B, January 2018.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.modules.data import BinaryResult
from src.utils.types import RollRecord


# ---------------------------------------------------------------------------
# Entropy source validation (NIST SP 800-90B Section 3)
# ---------------------------------------------------------------------------

def check_server_seed_min_entropy(
    records: List[RollRecord],
    threshold_bits: float,
) -> BinaryResult:
    """
    Validates that the server seed entropy source meets the minimum
    min-entropy threshold derived from NIST SP 800-90B Section 3.

    Computes empirical min-entropy from the observed server seed distribution:
        H_min = -log2(p_max)
    where p_max is the proportion of the most frequently observed seed value.
    PASS confirms no single seed dominates the distribution beyond the
    acceptable threshold; FAIL indicates the entropy source may be degraded.

    The sample_bound_bits field in the result records log2(n_seeds), which is
    the maximum H_min estimable from the available sample — the theoretical
    minimum for cryptographic seeds is much higher (>= 128 bits) and cannot
    be confirmed from roll records alone.
    """
    seeds = [r.server_seed for r in records]
    n = len(seeds)
    counts = Counter(seeds)
    max_count = max(counts.values())
    max_prob = max_count / n
    min_entropy = -math.log2(max_prob)
    sample_bound = math.log2(n)
    passed = min_entropy >= threshold_bits
    message = (
        f"Server seed min-entropy {min_entropy:.4f} bits meets the "
        f"threshold of {threshold_bits} bits."
        if passed
        else
        f"Server seed min-entropy {min_entropy:.4f} bits is below the "
        f"threshold of {threshold_bits} bits — entropy source may be degraded."
    )
    return BinaryResult(
        test_name="server_seed_min_entropy",
        passed=passed,
        message=message,
        details={
            "n_seeds": n,
            "n_unique_seeds": len(counts),
            "max_observed_frequency": max_count,
            "min_entropy_bits": round(min_entropy, 4),
            "threshold_bits": threshold_bits,
            "sample_bound_bits": round(sample_bound, 4),
        },
    )


# ---------------------------------------------------------------------------
# Runtime monitoring result type
# ---------------------------------------------------------------------------

@dataclass
class MonitorResult:
    alarms_triggered: int
    alarm_positions: List[int]
    passed: bool
    parameters_used: Dict[str, Any] = field(default_factory=dict)


def repetition_count_test(samples: list, threshold_c: int) -> MonitorResult:
    """
    Detects runs of identical consecutive values that exceed a threshold.

    The test scans the sample sequence from left to right, tracking the
    current run length of any repeating value. Each time the run length
    reaches threshold_c, an alarm fires and the run counter resets so that
    continued repetition of the same value fires further alarms at every
    subsequent repeat.

    This matches the NIST SP 800-90B Section 4.4.1 procedure: an alarm fires
    when C consecutive samples are identical, indicating the effective entropy
    per sample has dropped below the acceptable level.
    """
    if threshold_c < 2:
        raise ValueError(
            f"threshold_c must be >= 2. Got {threshold_c}."
        )
    if len(samples) == 0:
        raise ValueError("samples must not be empty.")

    alarm_positions: List[int] = []
    current_run = 1

    for i in range(1, len(samples)):
        if samples[i] == samples[i - 1]:
            current_run += 1
            if current_run >= threshold_c:
                alarm_positions.append(i)
                # Reset to 1 so continued repetition fires again after one more repeat
                current_run = 1
        else:
            current_run = 1

    alarms = len(alarm_positions)

    return MonitorResult(
        alarms_triggered=alarms,
        alarm_positions=alarm_positions,
        passed=alarms == 0,
        parameters_used={
            "n_samples": len(samples),
            "threshold_c": threshold_c,
        },
    )


def adaptive_proportion_test(
    samples: list,
    window_w: int,
    threshold: int,
) -> MonitorResult:
    """
    Detects over-representation of any single value within a sliding window.

    The test moves a window of width W across the sample sequence one step at
    a time. At each position, it counts how often each distinct value appears
    within the window. If any value's count meets or exceeds the threshold, an
    alarm fires at that window's end position.

    This matches the NIST SP 800-90B Section 4.4.2 sliding-window procedure.
    It catches entropy degradation that the Repetition Count Test misses: a
    source where the same value appears frequently but not consecutively will
    pass the repetition check but fail here.
    """
    if window_w < 2:
        raise ValueError(f"window_w must be >= 2. Got {window_w}.")
    if window_w > len(samples):
        raise ValueError(
            f"window_w ({window_w}) must not exceed the number of samples ({len(samples)})."
        )
    if threshold < 1:
        raise ValueError(f"threshold must be >= 1. Got {threshold}.")
    if len(samples) == 0:
        raise ValueError("samples must not be empty.")

    alarm_positions: List[int] = []

    # Build the initial window count
    counts: Dict[Any, int] = {}
    for i in range(window_w):
        val = samples[i]
        counts[val] = counts.get(val, 0) + 1

    def _check_alarm(position: int) -> None:
        if any(c >= threshold for c in counts.values()):
            alarm_positions.append(position)

    _check_alarm(window_w - 1)

    # Slide the window one step at a time
    for i in range(window_w, len(samples)):
        # Add the incoming sample
        incoming = samples[i]
        counts[incoming] = counts.get(incoming, 0) + 1

        # Remove the outgoing sample
        outgoing = samples[i - window_w]
        counts[outgoing] -= 1
        if counts[outgoing] == 0:
            del counts[outgoing]

        _check_alarm(i)

    alarms = len(alarm_positions)

    return MonitorResult(
        alarms_triggered=alarms,
        alarm_positions=alarm_positions,
        passed=alarms == 0,
        parameters_used={
            "n_samples": len(samples),
            "window_w": window_w,
            "threshold": threshold,
        },
    )