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


def get_mechanism_mapping_fn():
    """
    Utility function to centralize switching mechanism outcome functions.
    """
    # return stake_dice_outcome;
    return betswirl_dice_outcome;
    # return blockrand_dice_outcome;


def get_mechanism(data_file_path: str) -> ProvablyFairDiceMechanism:
    """
    Utility function to centralize switching mechanism instances.
    """
    # return StakesHMACMechanism(output_file=data_file_path)
    return BetSwirlChainlinkMechanism(output_file=data_file_path)
    # return BlockRandDrandMechanism(output_file=data_file_path)


def get_evaluation_configs() -> EvaluationConfig:
    """
    Utility function to centralize configuring evaluation configs.
    """
    return EvaluationConfig(
        n_faces=100, # outcomes between 1 and 100 inclusive
        distribution_min_rolls=500,
        n_latency_requests = 100,
        n_startup_requests = 200,
        n_load_requests = 100
    )
