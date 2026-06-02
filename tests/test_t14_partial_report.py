"""
T-14: Partial Report from Halted Evaluation

When evaluation halts at Light tier (e.g. because bareSHA256Check fails in
NPER), all domain result fields are None. The report engine must render a
valid, non-empty HTML report without crashing, and must not include empty
placeholder sections for uncompleted tiers.
"""
import os

from src.enigines.evaluation import EvaluationResult
from src.enigines.report import ReportEngine


def test_partial_report_renders_without_crashing(tmp_path):
    partial = EvaluationResult(
        mechanism="SHA-256 Concat Mechanism",
        tier="LIGHT",
        saved_at="2024-01-01 00:00:00",
        halted_at="LIGHT",
    )

    nper = {"bareSHA256Check": False, "csprngCompliance": True}

    report_engine = ReportEngine(str(tmp_path / "report.html"), n_faces=6)
    report_path = report_engine.generate(partial, [], "LIGHT", non_programmable=nper)

    assert os.path.exists(report_path)
    content = open(report_path, encoding="utf-8").read()
    assert len(content) > 100
    assert "SHA-256 Concat Mechanism" in content
