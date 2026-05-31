import argparse

from src.config.configs import MAX_VALUE
from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.provably_fair_mechanisms.chainlink_vrf_mechanism import BetSwirlChainlinkMechanism, betswirl_dice_outcome
from src.provably_fair_mechanisms.drand_mechanism import BlockRandDrandMechanism, blockrand_dice_outcome
from src.provably_fair_mechanisms.hmac_mechanism import StakesHMACMechanism, stake_dice_outcome
from src.utils.data_loader import load_roll_records_from

# Unifrom configuration for all evaluations. Adjust as needed for different scenarios.
CONFIG = EvaluationConfig(
    n_faces=MAX_VALUE,
    distribution_min_rolls=500,
)

# IGNORE THIS: For demonstration, I hardcode the mechanisms and their associated files here.
mechanisms_under_evaluation = {
    "OFF_CHAIN_HMAC": {
        "mechanism": StakesHMACMechanism(output_file="data/rolls/hmac_rolls.csv"),
        "rolls_file": "data/rolls/hmac_rolls.csv",
        "results_file": "data/results/hmac_eval_results.json",
    },
    "CHAINLINK_VRF": {
        "mechanism": BetSwirlChainlinkMechanism(output_file="data/rolls/chainlink_vrf_rolls.csv"),
        "rolls_file": "data/rolls/chainlink_vrf_rolls.csv",
        "results_file": "data/results/chainlink_vrf_eval_results.json",
    },
    "DRAND": {
        "mechanism": BlockRandDrandMechanism(output_file="data/rolls/drand_rolls.csv"),
        "rolls_file": "data/rolls/drand_rolls.csv",
        "results_file": "data/results/drand_eval_results.json",
    },
}

SELECTED_MECHANISM = "DRAND" # IGNORE THIS: For demonstration, I hardcode the mechanism selection here.


def main():
    parser = argparse.ArgumentParser(
        description="Provably Fair Dice Evaluation Framework",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of rolls to generate. If 0, loads existing rolls from the rolls file.",
    )
    parser.add_argument(
        "--tier",
        choices=["LIGHT", "IN_DEPTH", "FULL_DEPTH"],
        default="LIGHT",
        help="Evaluation depth tier (default: LIGHT).",
    )
    args = parser.parse_args()
    
    mechanism: ProvablyFairDiceMechanism = mechanisms_under_evaluation[SELECTED_MECHANISM]["mechanism"]
    results_file_path: str = mechanisms_under_evaluation[SELECTED_MECHANISM]["results_file"]
    rolls_file_path: str = mechanisms_under_evaluation[SELECTED_MECHANISM]["rolls_file"]

    if args.count > 0:
        rolls = mechanism.generate_rolls(quantity=args.count)
    else:
        rolls = load_roll_records_from(rolls_file_path)

    engine = EvaluationEngine(
        mechanism=mechanism,
        config=CONFIG,
        results_file_path=results_file_path,
    )

    # Each mechanism has its own bytes-to-outcome formula.
    mapping_fns = {
        "OFF_CHAIN_HMAC": stake_dice_outcome,
        "CHAINLINK_VRF": betswirl_dice_outcome,
        "DRAND": blockrand_dice_outcome,
    }

    engine.run_evaluation(
        rolls=rolls,
        tier=args.tier,
        mapping_fn=mapping_fns[SELECTED_MECHANISM],
    )


if __name__ == "__main__":
    """
    Usage: python -m src.main optional[--count <quanitiy>] --tier <LIGHT|IN_DEPTH|FULL_DEPTH>
    python -m src.main --count 1000 --tier LIGHT
    """
    main()
