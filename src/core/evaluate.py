"""
Script to run system:

--d NAME    : Filename of the rolls file (no extension) - REQUIRED
--r NAME    : Filename for the evaluation results (no extension) - REQUIRED
--t TIER    : Evaluation depth tier (LIGHT, IN_DEPTH, FULL_DEPTH) - default LIGHT

"""


import argparse
from typing import List

from src.config.configs import PER_DIRECTORY, ROLLS_DIRECTORY
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
        help="The filename for the evaluation results (no extension)",
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
        help="The filename of the rolls file (no extension)",
    )
    args = parser.parse_args()
    
    rolls_filepath = f"{ROLLS_DIRECTORY}/{args.d}.csv"
    per_filepath = f"{PER_DIRECTORY}/{args.r}.json"
    
    # Get mechanism instance and evaluation configs
    mechanism: ProvablyFairDiceMechanism = get_mechanism(data_file_path=rolls_filepath)
    configs: EvaluationConfig = get_evaluation_configs()
    
    # Get generated rolls from file
    rolls: List[RollRecord] = load_roll_records_from(file=rolls_filepath)
    
    # Initialize evaluation engine
    engine = EvaluationEngine(
        mechanism=mechanism,
        config=configs,
        results_file_path=per_filepath,
    )
    
    # Run evaluation engine
    engine.run_evaluation(
        rolls=rolls,
        tier=args.t,
        mapping_fn=get_mechanism_mapping_fn(),
    )


if __name__ == "__main__":
    """
    Usage: python -m src.core.evaluate --d NAME --r NAME --t TIER
    """
    main()
