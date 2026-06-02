"""
T-12: Uniform but Non-Independent Output Detection

A sorted sequence of 1000 uniformly-spaced float outcomes in [0, 100] has a
perfectly uniform marginal distribution — the Cramér-von Mises test sees a
continuous empirical CDF that exactly matches the theoretical uniform CDF and
passes. However the sequence is completely monotone: after binarising
(above/below median of ~50), the first 500 values are all 0 and the last 500
are all 1, producing only 2 runs instead of ~501 expected. The runs independence
test catches this with |z| ≈ 90 and fails. Both results are recorded separately.
"""
from src.enigines.config import EvaluationConfig
from src.modules.randomness.distribution_tests import cramer_von_mises_test, runs_independence_test


def test_uniform_but_non_independent_sequence():
    config = EvaluationConfig(n_faces=6)

    # Sorted float outcomes: uniformly spread over [0, 100] — distribution is
    # uniform but the sequence is monotone (maximally dependent).
    n = 1000
    outcomes = [i * 100.0 / (n - 1) for i in range(n)]

    cvm_result = cramer_von_mises_test(outcomes, config)
    runs_result = runs_independence_test(outcomes, config)

    assert cvm_result.passed, f"CVM unexpectedly failed: p={cvm_result.p_value}"
    assert not runs_result.passed, f"Runs test unexpectedly passed: p={runs_result.p_value}"

    assert cvm_result.p_value is not None
    assert runs_result.p_value is not None
