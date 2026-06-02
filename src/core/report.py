"""
The standalone script to produce the HTML report for the combined
evaluation results.
"""

import argparse
import json
import os
from typing import List, Optional

from src.config.configs import MAX_VALUE, NPER_DIRECTORY, PER_DIRECTORY, REPORTS_DIRECTORY, ROLLS_DIRECTORY
from src.enigines.evaluation import EvaluationResult
from src.enigines.report import ReportEngine
from src.modules.data import BinaryResult, TestResult
from src.modules.randomness.entropy_monitoring import MonitorResult
from src.modules.randomness.randomness_tests import (
    RandomnessEvaluationResult,
    RandomnessInDepthEvaluationResult,
    RandomnessLightEvaluationResult,
)
from src.modules.randomness.sanity_check import SanityCheckResult
from src.modules.security.security_tests import (
    SecurityEvaluationResult,
    SecurityLightEvaluationResult,
)
from src.modules.transparency.transparency_tests import (
    TransparencyEvaluationResult,
    TransparencyLightEvaluationResult,
)
from src.utils.data_loader import load_roll_records_from
from src.utils.types import RollRecord


def _binary_result(d: dict) -> BinaryResult:
    return BinaryResult(
        test_name=d["test_name"],
        passed=d["passed"],
        message=d["message"],
        details=d.get("details", {}),
    )


def _test_result(d: dict) -> TestResult:
    return TestResult(
        test_name=d["test_name"],
        p_value=d["p_value"],
        passed=d["passed"],
        parameters_used=d.get("parameters_used", {}),
    )


def _sanity_check_result(d: dict) -> SanityCheckResult:
    return SanityCheckResult(
        passed=d["passed"],
        chi_square_stat=d["chi_square_stat"],
        p_value=d["p_value"],
        message=d["message"],
    )


def _monitor_result(d: dict) -> MonitorResult:
    return MonitorResult(
        alarms_triggered=d["alarms_triggered"],
        alarm_positions=d["alarm_positions"],
        passed=d["passed"],
        parameters_used=d.get("parameters_used", {}),
    )


def _randomness_light(d: dict) -> RandomnessLightEvaluationResult:
    nist_light = None
    if d.get("nist_light"):
        nist_light = {k: _test_result(v) for k, v in d["nist_light"].items()}
    return RandomnessLightEvaluationResult(
        sanity_check=_sanity_check_result(d["sanity_check"]),
        cramer_von_mises=_test_result(d["cramer_von_mises"]),
        runs_independence=_test_result(d["runs_independence"]),
        server_seed_min_entropy=_binary_result(d["server_seed_min_entropy"]),
        nist_light=nist_light,
    )


def _randomness_in_depth(d: dict) -> RandomnessInDepthEvaluationResult:
    nist_in_depth = None
    if d.get("nist_in_depth"):
        nist_in_depth = {k: _test_result(v) for k, v in d["nist_in_depth"].items()}
    entropy_monitoring = {}
    if d.get("entropy_monitoring"):
        entropy_monitoring = {k: _monitor_result(v) for k, v in d["entropy_monitoring"].items()}
    return RandomnessInDepthEvaluationResult(
        nist_in_depth=nist_in_depth,
        entropy_monitoring=entropy_monitoring,
    )


def _randomness_result(d: dict) -> RandomnessEvaluationResult:
    return RandomnessEvaluationResult(
        n_rolls=d["n_rolls"],
        n_bits=d["n_bits"],
        light=_randomness_light(d["light"]) if d.get("light") else None,
        in_depth=_randomness_in_depth(d["in_depth"]) if d.get("in_depth") else None,
    )


def _security_light(d: dict) -> SecurityLightEvaluationResult:
    return SecurityLightEvaluationResult(
        seed_reuse=_binary_result(d["seed_reuse"]),
        nonce_presence=_binary_result(d["nonce_presence"]),
        nonce_uniqueness=_binary_result(d["nonce_uniqueness"]),
        nonce_min_entropy=d["nonce_min_entropy"],
    )


def _security_result(d: dict) -> SecurityEvaluationResult:
    return SecurityEvaluationResult(
        n_rolls=d["n_rolls"],
        light=_security_light(d["light"]) if d.get("light") else None,
    )


def _transparency_light(d: dict) -> TransparencyLightEvaluationResult:
    return TransparencyLightEvaluationResult(
        determinism=_binary_result(d["determinism"]),
        mapping_reproducibility=_binary_result(d["mapping_reproducibility"]),
    )


def _transparency_result(d: dict) -> TransparencyEvaluationResult:
    return TransparencyEvaluationResult(
        n_rolls=d["n_rolls"],
        light=_transparency_light(d["light"]) if d.get("light") else None,
    )


def _load_evaluation_result(path: str) -> EvaluationResult:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return EvaluationResult(
        mechanism=d["mechanism"],
        tier=d["tier"],
        saved_at=d["saved_at"],
        randomness=_randomness_result(d["randomness"]) if d.get("randomness") else None,
        security=_security_result(d["security"]) if d.get("security") else None,
        transparency=_transparency_result(d["transparency"]) if d.get("transparency") else None,
    )


def _load_nper(path: Optional[str]) -> Optional[dict]:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def main() -> None:
    parser = argparse.ArgumentParser(description="PFDM Report Generator")
    parser.add_argument(
        "--r",
        type=str,
        required=True,
        help="The name of the programmable evaluation results (per) file (no extension)"
    )
    parser.add_argument(
        "--np",
        type=str,
        required=True,
        help="The name of the non-programmable evaluation results (nper) file (no extension)"
    )
    parser.add_argument(
        "--d",
        type=str,
        required=True,
        help="The name of the generated rolls file (no extension)"
    )
    args = parser.parse_args()

    per_filepath = f"{PER_DIRECTORY}/{args.r}.json"
    nper_filepath = f"{NPER_DIRECTORY}/{args.np}.json"
    rolls_filepath = f"{ROLLS_DIRECTORY}/{args.d}.csv"

    programmable = _load_evaluation_result(per_filepath)
    non_programmable = _load_nper(nper_filepath)
    rolls: List[RollRecord] = load_roll_records_from(rolls_filepath)

    output_path = os.path.join(REPORTS_DIRECTORY, f"{args.r}.html")

    engine = ReportEngine(output_path=output_path, n_faces=MAX_VALUE)
    report_path = engine.generate(
        programmable=programmable,
        rolls=rolls,
        tier=programmable.tier,
        non_programmable=non_programmable,
    )
    print(f"Report generated: {report_path}")


if __name__ == "__main__":
    """
    Args:
        --d  : The filepath to the generated rolls CSV - REQUIRED
        --r  : The filepath to the programmable evaluation results (per) JSON - REQUIRED
        --np : The filepath to the non-programmable evaluation results (nper) JSON - REQUIRED

    Usage: python -m src.core.report --r NAME --d NAME --np NAME
    """
    main()
