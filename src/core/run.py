"""
The standalone script to run the full pipeline: generate rolls, evaluate them
and produce the HTML report in one command.
"""

import argparse
import json
import os
from typing import List, Optional

from src.config.configs import MAX_VALUE, NPER_DIRECTORY, PER_DIRECTORY, PROJECT_ROOT, REPORTS_DIRECTORY, ROLLS_DIRECTORY
from src.core.get_inputs import get_evaluation_configs, get_mechanism, get_mechanism_mapping_fn
from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.enigines.report import ReportEngine
from src.utils.types import RollRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PFDM Full Pipeline Runner"
    )
    parser.add_argument(
        "--c",
        type=int,
        default=1000,
        help="The number of rolls to generate (default: 1000)"
    )
    parser.add_argument(
        "--t",
        choices=["LIGHT", "IN_DEPTH", "FULL_DEPTH"],
        default="LIGHT",
        help="Evaluation depth tier (default: LIGHT)",
    )
    parser.add_argument(
        "--d",
        type=str,
        required=True,
        help="The name of the rolls file (no extension)"
    )
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
        "--o",
        type=str,
        required=False,
        help="The name of the output report file (no extension). Defaults to the same name as the per file.",
    )
    args = parser.parse_args()

    rolls_filepath = f"{ROLLS_DIRECTORY}/{args.d}.csv"
    per_filepath = f"{PER_DIRECTORY}/{args.r}.json"
    nper_filepath = f"{NPER_DIRECTORY}/{args.np}.json"

    # Step 1: Generate rolls
    mechanism: ProvablyFairDiceMechanism = get_mechanism(data_file_path=rolls_filepath)
    rolls: List[RollRecord] = mechanism.generate_rolls(quantity=args.c)

    # Step 2: Evaluate
    configs: EvaluationConfig = get_evaluation_configs()
    eval_engine = EvaluationEngine(
        mechanism=mechanism,
        config=configs,
        results_file_path=per_filepath,
    )
    result = eval_engine.run_evaluation(
        rolls=rolls,
        tier=args.t,
        mapping_fn=get_mechanism_mapping_fn(),
    )

    # Step 3: Generate report
    with open(nper_filepath, "r", encoding="utf-8") as f:
        non_programmable = json.load(f)
    
    filename = args.o if args.o else args.r
    output_path = os.path.join(REPORTS_DIRECTORY, f"{filename}.html")

    report_engine = ReportEngine(output_path=output_path, n_faces=MAX_VALUE)
    report_path = report_engine.generate(
        programmable=result,
        rolls=rolls,
        tier=result.tier,
        non_programmable=non_programmable,
    )
    print(f"Report generated: {os.path.relpath(report_path, PROJECT_ROOT)}")


if __name__ == "__main__":
    """
    Args:
        --c  : The number of rolls to generate (default: 1000)
        --d  : The filepath to save the generated rolls CSV - REQUIRED
        --r  : The filepath to save the programmable evaluation results (per) JSON - REQUIRED
        --np : The filepath to the non-programmable evaluation results (nper) JSON - REQUIRED
        --o  : The filename for the output report (no extension). 
        
    Usage: python -m src.core.run --c COUNT --d NAME --r NAME --np NAME --o filename
    """
    main()
