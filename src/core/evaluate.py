"""
Script to run system:

--c COUNT: Number of rolls to generate. Default is 1000
--t TIER: Evaluation depth tier (LIGHT, IN_DEPTH, FULL_DEPTH). Default is LIGHT.
--d path/to/rolls.csv: The file path to save generated rolls. REQUIRED
--r path/to/results.json: The file path to save evaluation results. REQUIRED
--np path/to/nper.json: The file path to collected nper values REQUIRED


generate_rolls: python src.core.rolls --c COUNT --d DATA_PATH

evaluate: python src.core.evaluate --r RESULTS_PATH --t TIER --d DATA_PATH

report: python src.core.report --r RESULTS_PATH --np NPER_PATH

run_all: python src.core.run_all --c COUNT --t TIER --d DATA_PATH --r RESULTS_PATH --np NPER_PATH

"""


import argparse
from typing import List

from src.core.get_inputs import get_evaluation_configs, get_mechanism, get_mechanism_mapping_fn
from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.utils.data_loader import load_roll_records_from
from src.utils.types import RollRecord



def main():
    parser = argparse.ArgumentParser(
        description="PFDM Evaluator",
    )
    parser.add_argument(
        "--r",
        type=str,
        required=True,
        help="The file path to save evaluation results",
    )
    parser.add_argument(
        "--t",
        choices=["LIGHT", "IN_DEPTH", "FULL_DEPTH"],
        default="LIGHT",
        help="The evaluation depth tier (default: LIGHT)",
    )
    parser.add_argument(
        "--d",
        type=str,
        required=True,
        help="The file path to load rolls from",
    )
    args = parser.parse_args()
    
    # Get mechanism instance and evaluation configs
    mechanism: ProvablyFairDiceMechanism = get_mechanism(data_file_path=args.d)
    configs: EvaluationConfig = get_evaluation_configs()
    
    # Get generated rolls from file
    rolls: List[RollRecord] = load_roll_records_from(file=args.d)
    
    # Initialize evaluation engine
    engine = EvaluationEngine(
        mechanism=mechanism,
        config=configs,
        results_file_path=args.r,
    )
    
    # Run evaluation engine
    engine.run_evaluation(
        rolls=rolls,
        tier=args.t,
        mapping_fn=get_mechanism_mapping_fn(),
    )


if __name__ == "__main__":
    """
    Usage: python -m src.core.evaluate --r path/to/evaluation_results.json --t TIER --d path/to/rolls.csv
    """
    main()
