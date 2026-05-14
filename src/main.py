
import argparse
from typing import List

from src.enigines.evaluation import EvaluationEngine
from src.provably_fair_mechanisms.chainlink_vrf import ChainlinkVRFMechanism
from src.provably_fair_mechanisms.drand_mechanism import DrandMechanism
from src.provably_fair_mechanisms.hmac_mechanism import HMACMechanism


def main():
    # ============================ ARGUMENTS ============================

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of rolls to generate.",
    )
    args = parser.parse_args()
    
    HAMC_OUTPUT = "data/rolls/hmac_rolls.csv"
    DRAND_OUTPUT = "data/rolls/drand_rolls.csv"
    CHAINLINK_OUTPUT = "data/rolls/chainlink_vrf_rolls.csv"

    # ========================= Setup Mechanisms =========================
    
    hmac = HMACMechanism(output_file=HAMC_OUTPUT)
    drand = DrandMechanism(output_file=DRAND_OUTPUT)
    
    # Note: High quanities may take a while due to very slow fulliment rates.
    chainlink_vrf = ChainlinkVRFMechanism(output_file=CHAINLINK_OUTPUT)
    
    # ========================= Evaluation Engine =========================
    
    hmac_rolls = hmac.generate_rolls(args.count)
    hmac_eval = EvaluationEngine(mechanism=hmac)
    hmac_eval.evaluate_randomness(hmac_rolls)



if __name__ == "__main__":
    """
    Usage python -m src.main --count <number_of_rolls_to_generate_per_mechanism>
    """
    main()