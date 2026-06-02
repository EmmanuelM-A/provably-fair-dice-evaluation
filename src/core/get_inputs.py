"""
Centralized utility functions to get the necessary inputs for evalaution system.
"""

from src.config.configs import MAX_VALUE
from src.enigines.config import EvaluationConfig
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.provably_fair_mechanisms.chainlink_vrf_mechanism import BetSwirlChainlinkMechanism
from src.provably_fair_mechanisms.drand_mechanism import BlockRandDrandMechanism
from src.provably_fair_mechanisms.chainlink_vrf_mechanism import betswirl_dice_outcome
from src.provably_fair_mechanisms.drand_mechanism import blockrand_dice_outcome
from src.provably_fair_mechanisms.hmac_mechanism import StakesHMACMechanism, stake_dice_outcome

"""
Script to run system:

--c COUNT: Number of rolls to generate. Default is 1000
--t TIER: Evaluation depth tier (LIGHT, IN_DEPTH, FULL_DEPTH). Default is LIGHT.
--d path/to/rolls.csv: The file path to save generated rolls. REQUIRED
--r path/to/results.json: The file path to save evaluation results. REQUIRED
--np path/to/nper.json: The file path to collected nper values REQUIRED


generate_rolls: python -m src.core.rolls --c COUNT --d DATA_PATH

evaluate: python -m src.core.evaluate --r RESULTS_PATH --t TIER --d DATA_PATH

report: python -m src.core.report --r RESULTS_PATH --np NPER_PATH

run_all: python -m src.core.run_all --c COUNT --t TIER --d DATA_PATH --r RESULTS_PATH --np NPER_PATH

"""

def get_mechanism_mapping_fn():
    """
    Utility function to centralize switching mechanism outcome functions.
    """
    return stake_dice_outcome;
    # return betswirl_dice_outcome;
    # return blockrand_dice_outcome;


def get_mechanism(data_file_path: str) -> ProvablyFairDiceMechanism:
    """
    Utility function to centralize switching mechanism instances.
    """
    return StakesHMACMechanism(output_file=data_file_path)
    # return BetSwirlChainlinkMechanism(output_file=data_file_path)
    # return BlockRandDrandMechanism(output_file=data_file_path)


def get_evaluation_configs() -> EvaluationConfig:
    """
    Utility function to centralize configuring evaluation configs.
    """
    return EvaluationConfig(
        n_faces=MAX_VALUE, # 100 so all it produces outcomes [1, 100]
        distribution_min_rolls=500,
    )
