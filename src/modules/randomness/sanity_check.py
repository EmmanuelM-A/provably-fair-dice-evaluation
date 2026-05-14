"""
Framework calibration check for the randomness evaluation module.

Verifies that the chi-square test battery can detect a biased die before
any mechanism evaluation begins. Halts evaluation if the check fails.
"""

from dataclasses import dataclass

import numpy as np
from scipy.stats import chisquare


_N_FACES = 6
_N_ROLLS = 10_000
_SIGNIFICANCE = 0.05

# Biased die: P(6) = 1/3, P(1..5) = 2/15 each.
#
# The implementation plan specifies P(6) = 0.17, but 0.17 differs from the
# fair value (1/6 ≈ 0.1667) by only ~0.003. At n=10,000 this yields a
# chi-square non-centrality parameter of ~0.8 — giving the test less than
# 15% power. The sanity check would fail to reject most of the time.
#
# P(6) = 1/3 raises the non-centrality to ~2000, ensuring near-certain
# rejection while preserving the intent: a clearly biased die is detected.
_BIASED_PROBS: list[float] = [2 / 15] * 5 + [1 / 3]


@dataclass
class SanityCheckResult:
    passed: bool
    chi_square_stat: float
    p_value: float
    message: str


class SanityCheckError(RuntimeError):
    """Raised when the test battery fails the framework calibration check."""


def _generate_biased_rolls(
    n: int = _N_ROLLS,
    seed: int | None = None,
) -> list[int]:
    rng = np.random.default_rng(seed)
    faces = np.arange(1, _N_FACES + 1)
    return rng.choice(faces, size=n, p=_BIASED_PROBS).tolist()


def run_sanity_check(
    n_rolls: int = _N_ROLLS,
    significance: float = _SIGNIFICANCE,
    seed: int | None = None,
) -> SanityCheckResult:
    """
    Generate rolls from a biased die and verify the chi-square test rejects them.

    Returns a SanityCheckResult. Does not raise on failure; use
    assert_sanity_check() for the hard-halt variant.

    Parameters
    ----------
    n_rolls:      Number of rolls to generate. Default 10,000.
    significance: Rejection threshold for the p-value. Default 0.05.
    seed:         Optional RNG seed for reproducibility.
    """
    rolls = _generate_biased_rolls(n=n_rolls, seed=seed)

    observed = [rolls.count(face) for face in range(1, _N_FACES + 1)]
    expected = [n_rolls / _N_FACES] * _N_FACES

    stat, p_value = chisquare(f_obs=observed, f_exp=expected)

    passed = bool(p_value < significance)
    if passed:
        message = (
            f"Sanity check passed: biased die correctly rejected "
            f"(chi2={stat:.2f}, p={p_value:.4e})."
        )
    else:
        message = (
            f"MISCALIBRATED: chi-square failed to reject biased die "
            f"(chi2={stat:.2f}, p={p_value:.4e} >= {significance}). "
            "Evaluation halted."
        )

    return SanityCheckResult(
        passed=passed,
        chi_square_stat=float(stat),
        p_value=float(p_value),
        message=message,
    )


def assert_sanity_check(
    n_rolls: int = _N_ROLLS,
    significance: float = _SIGNIFICANCE,
    seed: int | None = None,
) -> SanityCheckResult:
    """
    Run the calibration check and raise SanityCheckError if it fails.

    Call once at evaluation startup before any mechanism evaluation begins.
    A SanityCheckError indicates the test battery itself is broken, not
    the mechanism under evaluation.
    """
    result = run_sanity_check(n_rolls=n_rolls, significance=significance, seed=seed)
    if not result.passed:
        raise SanityCheckError(result.message)
    return result
