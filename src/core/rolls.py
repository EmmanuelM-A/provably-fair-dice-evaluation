"""
The standalone script to generate the dice rolls for the evaluation.


--c COUNT   : Number of rolls to generate (default: 1000)
--d NAME    : Filename for the generated rolls (no extension) - REQUIRED


generate_rolls: python -m src.core.rolls --c COUNT --d NAME

evaluate:       python -m src.core.evaluate --d NAME --r NAME --t TIER

report:         python -m src.core.report --d NAME --r NAME --np NAME

run_all:        python -m src.core.run --c COUNT --t TIER --d NAME --r NAME --np NAME

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
    Usage: python -m src.core.rolls --c COUNT --d NAME
    """
    main()
