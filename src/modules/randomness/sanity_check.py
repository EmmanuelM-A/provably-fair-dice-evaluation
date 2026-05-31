"""
Framework calibration check for the randomness evaluation module.

Runs a chi-square uniformity test on the mechanism's actual roll outputs.
Flags biased outcomes before the main evaluation proceeds.
"""

from dataclasses import dataclass
from typing import List

import numpy as np
from scipy.stats import chisquare

from src.enigines.config import EvaluationConfig
from src.utils.types import RollRecord


@dataclass
class SanityCheckResult:
    passed: bool
    chi_square_stat: float
    p_value: float
    message: str


def run_sanity_check(
    rolls: List[RollRecord],
    configs: EvaluationConfig,
) -> SanityCheckResult:
    """
    Chi-square uniformity check on actual mechanism rolls.

    Bins outcomes into n_faces equal-width buckets using the observed range,
    which handles both integer outcomes (e.g. 1–100) and float outcomes
    (e.g. Stake's 0.00–100.00) without any sum mismatch.

    Raises RuntimeError if outcomes are biased (p < significance_level).
    """
    outcomes = np.array([r.outcome for r in rolls], dtype=float)
    n_rolls = len(outcomes)
    n_faces = configs.n_faces
    significance = configs.significance_level

    # np.histogram auto-range includes all data, so sum(observed) == n_rolls always.
    observed, _ = np.histogram(outcomes, bins=n_faces)
    expected = np.full(n_faces, n_rolls / n_faces, dtype=float)

    stat, p_value = chisquare(f_obs=observed.astype(float), f_exp=expected)

    is_biased = bool(p_value < significance)

    if is_biased:
        message = (
            f"Biased outcomes detected "
            f"(chi2={stat:.2f}, p={p_value:.4e} < {significance}). "
            "Evaluation flagged!"
        )
        raise RuntimeError(message)

    message = (
        f"Sanity check passed: outcomes appear uniform "
        f"(chi2={stat:.2f}, p={p_value:.4e})."
    )

    return SanityCheckResult(
        passed=True,
        chi_square_stat=float(stat),
        p_value=float(p_value),
        message=message,
    )
