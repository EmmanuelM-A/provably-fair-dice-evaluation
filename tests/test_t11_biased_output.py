"""
T-11: Biased Output Detection via Chi-Square

The BiasedMechanism produces outcomes where P(face 6) = 1/3 instead of 1/6.
With 1000 rolls the sanity check chi-square statistic far exceeds the critical
value, so run_sanity_check raises RuntimeError. This propagates out of
EvaluationEngine.run_evaluation, confirming the test battery correctly flags
economically meaningful bias.
"""
import pytest

from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.provably_fair_mechanisms.baised_mechanism import BiasedMechanism


def test_biased_output_raises_runtime_error_via_engine(tmp_path):
    config = EvaluationConfig(n_faces=6)
    mechanism = BiasedMechanism(config)
    rolls = mechanism.generate_rolls(1000, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)

    with pytest.raises(RuntimeError, match="Biased outcomes detected"):
        engine.run_evaluation(rolls, "LIGHT")
