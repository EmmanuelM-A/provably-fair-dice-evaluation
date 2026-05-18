"""
Framework calibration check for the randomness evaluation module.

Verifies that the chi-square test battery can detect a biased die before
any mechanism evaluation begins. Halts evaluation if the check fails.
"""

from dataclasses import dataclass

from scipy.stats import chisquare

from src.enigines.config import EvaluationConfig
from src.provably_fair_mechanisms.baised_mechanism import BiasedMechanism
from src.utils.types import RollRecord


@dataclass
class SanityCheckResult:
    passed: bool
    chi_square_stat: float
    p_value: float
    message: str


def run_sanity_check(
    configs: EvaluationConfig,
) -> SanityCheckResult:
    """
    Runs a sanity check on the provided rolls by applying
    a chi-square test to verify it is correctly rejected.
    """
    
    rolls = BiasedMechanism(config=configs).generate_rolls(quantity=configs.distribution_min_rolls)
    
    outcomes = [r.outcome for r in rolls]
    n_rolls = len(outcomes)
    n_faces = configs.n_faces
    significance = configs.significance_level

    observed = [outcomes.count(face) for face in range(1, n_faces + 1)]
    expected = [n_rolls / n_faces] * n_faces

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
            "Evaluation halted!"
        )

    if not passed:
        raise RuntimeError(message)

    return SanityCheckResult(
        passed=passed,
        chi_square_stat=float(stat),
        p_value=float(p_value),
        message=message,
    )
