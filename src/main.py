
import argparse
from typing import List

from src.provably_fair_mechanisms.chainlink_vrf import ChainlinkVRFMechanism
from src.provably_fair_mechanisms.drand_mechanism import DrandMechanism
from src.provably_fair_mechanisms.hmac_mechanism import HMACMechanism
from src.enigines.pfd import ProvablyFairDiceMechanism


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
    
    mechanisms: List[ProvablyFairDiceMechanism] = []
    
    mechanisms.append(HMACMechanism())
    mechanisms.append(DrandMechanism())
    
    # Note: High quanity may take a while due to API rate limits.
    mechanisms.append(ChainlinkVRFMechanism())
    
    # ========================= Evaluation Engine =========================
    
    for mech in mechanisms:
        rolls = mech.generate_rolls(args.count, HAMC_OUTPUT)

    

if __name__ == "__main__":
    main()