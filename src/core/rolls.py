"""
The standalone script to generate the dice rolls for the evaluation.


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

from src.config.configs import ROLLS_DIRECTORY
from src.core.get_inputs import get_mechanism
from src.enigines.pfd import ProvablyFairDiceMechanism



def main():
    parser = argparse.ArgumentParser(
        description="PFDM Roll Generator",
    )
    parser.add_argument(
        "--c",
        type=int,
        default=1000,
        help="The number of rolls to generate (default: 1000).",
    )
    parser.add_argument(
        "--d",
        type=str,
        required=True,
        help="The filename to save generated rolls as",
    )
    args = parser.parse_args()
    
    filepath = f"{ROLLS_DIRECTORY}/{args.d}.csv"
    
    # Get mechanism instance
    mechanism: ProvablyFairDiceMechanism = get_mechanism(data_file_path=filepath)
    
    # Generate rolls and save to file
    mechanism.generate_rolls(quantity=args.c)


if __name__ == "__main__":
    """
    Usage: python -m src.core.rolls --c COUNT --d path/to/rolls.csv
    """
    main()
