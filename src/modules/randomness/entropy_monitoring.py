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