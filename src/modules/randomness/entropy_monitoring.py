"""
Runtime entropy monitoring for ongoing randomness quality assessment.

Implements two tests drawn from NIST SP 800-90B Section 4.4:
- repetition_count_test: Detects consecutive repeated values
- adaptive_proportion_test: Detects over-representation within a sliding window

Both tests are designed for runtime monitoring across the full sequence of
observed outputs, not just a one-time snapshot. They scan the entire sample
list and record every position where an alarm fires, so degradation at any
point in the sequence is captured.

Each returns a MonitorResult with:
- alarms_triggered: total number of alarms fired
- alarm_positions: list of sample indices where each alarm fired
- passed: True if no alarms were triggered

Reference: Turan et al., "Recommendation for the Entropy Sources Used for
Random Bit Generation", NIST SP 800-90B, January 2018, Section 4.4.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MonitorResult:
    alarms_triggered: int
    alarm_positions: List[int]
    passed: bool
    parameters_used: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Test 1: Repetition Count Test
# ---------------------------------------------------------------------------

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

    Parameters
    ----------
    samples : list
        Ordered sequence of observed outputs in generation order. Values
        may be any comparable type (int, bytes, str).
    threshold_c : int
        Number of consecutive identical values that triggers an alarm.
        Must be >= 2. Derive this from the entropy estimate of your source:
        C = ceil(1 / H) where H is the min-entropy per sample in bits,
        or use C = 20 as a conservative default for a uniform 6-face die.

    Returns
    -------
    MonitorResult
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


# ---------------------------------------------------------------------------
# Test 2: Adaptive Proportion Test
# ---------------------------------------------------------------------------

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

    Parameters
    ----------
    samples : list
        Ordered sequence of observed outputs in generation order.
    window_w : int
        Width of the sliding window in samples. Must be >= 2 and <= len(samples).
        NIST SP 800-90B recommends W = 512 for binary sources; for a 6-face die
        a window of 512 to 1024 rolls is appropriate.
    threshold : int
        Maximum number of times any single value may appear within one window
        before an alarm fires. Must be >= 1.
        Derive from the acceptable false-positive rate and the expected
        per-value probability: threshold = C where P(count >= C) < alpha
        under the null hypothesis of uniform output.
        For a 6-face die with W=512, a conservative threshold is 120
        (expected count ~85 under uniformity, threshold set at ~99th percentile).

    Returns
    -------
    MonitorResult

    Notes
    -----
    An alarm at position i means the window ending at sample index i contained
    a value that appeared >= threshold times. Multiple alarms within overlapping
    windows covering the same anomaly are recorded separately; alarm_positions
    contains every window-end index that triggered.

    Runtime is O(n * W) in the naive case. The implementation uses an
    incremental counter dict that updates in O(1) per step, giving O(n) overall.
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