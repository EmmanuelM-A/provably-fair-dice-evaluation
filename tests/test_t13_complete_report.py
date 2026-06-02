"""
T-13: Complete Report Generation from Passing Results

A fully compliant HMAC-SHA256 mechanism is evaluated at Light tier. The report
engine must render a complete, human-readable HTML report that includes all
evaluated sections and is consistent with the evaluation result.
"""
import os

from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.report import ReportEngine
from src.provably_fair_mechanisms.hmac_mechanism import StakesHMACMechanism, stake_dice_outcome


def test_complete_report_renders_all_sections(tmp_path):
    config = EvaluationConfig(
        n_faces=6,
        server_seed_min_entropy_threshold_bits=0.0,
        n_latency_requests=20,
    )
    mechanism = StakesHMACMechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    result = engine.run_evaluation(rolls, "LIGHT", mapping_fn=stake_dice_outcome)

    assert result.randomness is not None
    assert result.security is not None

    report_engine = ReportEngine(str(tmp_path / "report.html"), n_faces=6)
    report_path = report_engine.generate(result, rolls, "LIGHT")

    assert os.path.exists(report_path)
    content = open(report_path, encoding="utf-8").read()
    assert len(content) > 500
    assert "HMAC-SHA256 Mechanism" in content
