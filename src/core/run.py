"""
Full pipeline runner — generates rolls, evaluates them, and produces the HTML report in one command.

Usage:
    python -m src.core.run --d DATA_PATH --r RESULTS_PATH [--c COUNT] [--t TIER] [--np NPER_PATH] [--o REPORT_PATH]

Args:
    --c  : Number of rolls to generate (default: 1000)
    --t  : Evaluation depth tier — LIGHT | IN_DEPTH | FULL_DEPTH (default: LIGHT)
    --d  : Path to save the generated rolls CSV (required)
    --r  : Path to save the evaluation results JSON (required)
    --np : Path to an existing non-programmable evaluation results JSON (optional)
    --o  : Output path for the HTML report (optional; defaults to --r with .html extension)
"""

import argparse
import json
import os
from typing import List, Optional

from src.config.configs import MAX_VALUE
from src.core.get_inputs import get_evaluation_configs, get_mechanism, get_mechanism_mapping_fn
from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.enigines.report import ReportEngine
from src.utils.types import RollRecord


def main() -> None:
    parser = argparse.ArgumentParser(description="PFDM Full Pipeline Runner")
    parser.add_argument("--c", type=int, default=1000, help="Number of rolls to generate (default: 1000)")
    parser.add_argument(
        "--t",
        choices=["LIGHT", "IN_DEPTH", "FULL_DEPTH"],
        default="LIGHT",
        help="Evaluation depth tier (default: LIGHT)",
    )
    parser.add_argument("--d", type=str, required=True, help="Path to save generated rolls CSV")
    parser.add_argument("--r", type=str, required=True, help="Path to save evaluation results JSON")
    parser.add_argument("--np", type=str, required=False, default=None, help="Path to non-programmable evaluation results JSON")
    parser.add_argument("--o", type=str, required=False, default=None, help="Output path for the HTML report")
    args = parser.parse_args()

    output_path = args.o or os.path.splitext(args.r)[0] + ".html"

    # Step 1: Generate rolls
    mechanism: ProvablyFairDiceMechanism = get_mechanism(data_file_path=args.d)
    rolls: List[RollRecord] = mechanism.generate_rolls(quantity=args.c)

    # Step 2: Evaluate
    configs: EvaluationConfig = get_evaluation_configs()
    eval_engine = EvaluationEngine(
        mechanism=mechanism,
        config=configs,
        results_file_path=args.r,
    )
    result = eval_engine.run_evaluation(
        rolls=rolls,
        tier=args.t,
        mapping_fn=get_mechanism_mapping_fn(),
    )

    # Step 3: Generate report (non-programmable results are optional manual input)
    non_programmable: Optional[dict] = None
    if args.np and os.path.exists(args.np):
        with open(args.np, "r", encoding="utf-8") as f:
            non_programmable = json.load(f)

    report_engine = ReportEngine(output_path=output_path, n_faces=MAX_VALUE)
    report_path = report_engine.generate(
        programmable=result,
        rolls=rolls,
        tier=args.t,
        non_programmable=non_programmable,
    )
    print(f"Report generated: {report_path}")


if __name__ == "__main__":
    """
    Usage: python -m src.core.run --d path/to/rolls.csv --r path/to/results.json --np path/to/nper.json
    """
    main()
