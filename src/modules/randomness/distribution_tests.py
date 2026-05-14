"""
Distribution tests for randomness evaluation of dice roll outcomes.

Three tests are implemented:
- chi_square_test: Uniformity across all faces
- cramer_von_mises_test: Uniformity via empirical CDF distance
- runs_independence_test: Independence via run structure

Reference for chi-square validity: expected frequency per bin must be >= 5.
Minimum 500 rolls for chi-square across 100 bins; 10,000 recommended for
reliable sensitivity across all three tests.
"""

import math
from typing import List

import numpy as np
from scipy import stats

from src.modules.data import TestResult


SIGNIFICANCE_LEVEL = 0.01


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _check_min_rolls(outcomes: List[int], minimum: int, test_name: str) -> None:
    if len(outcomes) < minimum:
        raise ValueError(
            f"{test_name} requires at least {minimum} rolls. Got {len(outcomes)}."
        )


def _check_expected_frequency(n_rolls: int, n_bins: int, test_name: str) -> None:
    expected_per_bin = n_rolls / n_bins
    if expected_per_bin < 5:
        raise ValueError(
            f"{test_name}: expected frequency per bin is {expected_per_bin:.2f}, "
            f"which is below the minimum of 5. Provide at least {math.ceil(5 * n_bins)} rolls."
        )


# ---------------------------------------------------------------------------
# Test 1: Chi-Square Uniformity Test
# ---------------------------------------------------------------------------

def chi_square_test(
    outcomes: List[int],
    n_faces: int = 6,
    n_rolls: int = 10_000,
) -> TestResult:
    """
    Tests whether dice outcomes are uniformly distributed across all faces.

    Uses scipy.stats.chisquare with explicit expected frequencies.
    Expected frequency per bin must be >= 5 for the approximation to be valid;
    this is checked before the test runs.

    Parameters
    ----------
    outcomes : list of ints
        Observed dice roll outcomes. Each value must be in [1, n_faces].
    n_faces : int
        Number of faces on the die (default 6).
    n_rolls : int
        Expected total number of rolls. Used to set expected frequencies.
        The actual length of outcomes is used for observed counts; n_rolls
        is recorded in parameters_used for audit purposes.

    Returns
    -------
    TestResult
    """
    _check_min_rolls(outcomes, minimum=500, test_name="Chi-Square Test")

    n = len(outcomes)
    _check_expected_frequency(n, n_bins=n_faces, test_name="Chi-Square Test")

    observed = np.zeros(n_faces, dtype=float)
    for outcome in outcomes:
        if outcome < 1 or outcome > n_faces:
            raise ValueError(
                f"Outcome {outcome} is out of range [1, {n_faces}]."
            )
        observed[outcome - 1] += 1

    expected = np.full(n_faces, n / n_faces, dtype=float)

    chi_sq, p_value = stats.chisquare(f_obs=observed, f_exp=expected)

    return TestResult(
        test_name="Chi-Square Uniformity Test",
        p_value=float(p_value),
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n_rolls_observed": n,
            "n_rolls_expected_parameter": n_rolls,
            "n_faces": n_faces,
            "degrees_of_freedom": n_faces - 1,
            "expected_frequency_per_bin": n / n_faces,
            "chi_sq": float(chi_sq),
            "observed_counts": observed.tolist(),
        },
    )


# ---------------------------------------------------------------------------
# Test 2: Cramer-von Mises Uniformity Test
# ---------------------------------------------------------------------------

def cramer_von_mises_test(outcomes: List[int]) -> TestResult:
    """
    Tests whether dice outcomes follow a discrete uniform distribution by
    measuring the distance between the empirical CDF and the theoretical
    uniform CDF.

    Uses scipy.stats.cramervonmises with a uniform CDF argument.
    The test is two-sided (alternative='two-sided' is the only option for
    cramervonmises).

    Outcomes are normalised to [0, 1] before the test so that the continuous
    uniform CDF on [0, 1] is the correct reference. Normalisation uses
    (outcome - 1) / (n_faces - 1), which maps face 1 to 0.0 and face n_faces
    to 1.0.

    Parameters
    ----------
    outcomes : list of ints
        Observed dice roll outcomes. Values are used as-is to infer n_faces
        as max(outcomes).

    Returns
    -------
    TestResult
    """
    _check_min_rolls(outcomes, minimum=500, test_name="Cramer-von Mises Test")

    n = len(outcomes)
    arr = np.array(outcomes, dtype=float)
    n_faces = int(arr.max())

    if n_faces < 2:
        raise ValueError(
            "Cramer-von Mises Test requires at least 2 distinct faces. "
            f"Max outcome observed is {n_faces}."
        )

    normalised = (arr - 1.0) / (n_faces - 1.0)

    result = stats.cramervonmises(
        rvs=normalised,
        cdf="uniform",
        args=(0, 1),
    )

    return TestResult(
        test_name="Cramer-von Mises Uniformity Test",
        p_value=float(result.pvalue),
        passed=result.pvalue >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n_rolls": n,
            "n_faces_inferred": n_faces,
            "statistic": float(result.statistic),
            "normalisation": "(outcome - 1) / (n_faces - 1)",
            "reference_cdf": "uniform(0, 1)",
        },
    )


# ---------------------------------------------------------------------------
# Test 3: Runs Independence Test
# ---------------------------------------------------------------------------

def runs_independence_test(outcomes: List[int]) -> TestResult:
    """
    Tests whether consecutive dice outcomes are independent by examining the
    run structure of the sequence relative to its median.

    Each outcome is converted to a binary label: 1 if outcome > median,
    0 if outcome <= median. The number of runs (consecutive blocks of
    identical labels) is then compared against the expected distribution
    under independence using the Wald-Wolfowitz runs test.

    The p-value is derived from the normal approximation, which is reliable
    when both groups contain at least 10 observations.

    This is not the same as the NIST Runs Test, which operates on a bit
    sequence. This test operates on ordered integer outcomes and targets
    serial correlation at the outcome level.

    Parameters
    ----------
    outcomes : list of ints
        Observed dice roll outcomes in the order they were generated.

    Returns
    -------
    TestResult
    """
    _check_min_rolls(outcomes, minimum=500, test_name="Runs Independence Test")

    n = len(outcomes)
    arr = np.array(outcomes, dtype=float)
    median = float(np.median(arr))

    above = (arr > median).astype(int)

    n1 = int(np.sum(above == 1))
    n2 = int(np.sum(above == 0))

    if n1 < 10 or n2 < 10:
        raise ValueError(
            f"Runs Independence Test requires at least 10 observations above and "
            f"below the median. Got n_above={n1}, n_below={n2}. "
            "The outcome distribution may be too skewed for this test."
        )

    # Count runs
    runs = 1 + int(np.sum(above[:-1] != above[1:]))

    # Expected number of runs and variance under independence
    expected_runs = (2.0 * n1 * n2 / (n1 + n2)) + 1.0
    variance_runs = (
        2.0 * n1 * n2 * (2.0 * n1 * n2 - n1 - n2)
        / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    )
    std_runs = math.sqrt(variance_runs)

    z = (runs - expected_runs) / std_runs
    # Two-sided p-value from normal approximation
    p_value = 2.0 * (1.0 - stats.norm.cdf(abs(z)))
    
    passed = p_value >= SIGNIFICANCE_LEVEL

    return TestResult(
        test_name="Runs Independence Test",
        p_value=float(p_value),
        passed=passed,
        parameters_used={
            "n_rolls": n,
            "median": median,
            "n_above_median": n1,
            "n_below_or_equal_median": n2,
            "observed_runs": runs,
            "expected_runs": expected_runs,
            "variance_runs": variance_runs,
            "z_statistic": z,
        },
    )