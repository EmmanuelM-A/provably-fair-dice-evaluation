"""
Generates N roll records using Chainlink VRF v2.5 and writes them to a CSV file.

Required environment variables (see .env):
    VRF_RPC_URL             - Your Alchemy or Infura RPC endpoint
    VRF_CONSUMER_ADDRESS    - Address of your deployed consumer contract
    VRF_COORDINATOR_ADDRESS - Address of the VRF coordinator on the same network
    VRF_SENDER_ADDRESS      - The wallet address that pays for requests
    VRF_SENDER_PRIVATE_KEY  - Private key for that wallet (never hardcode this)

Usage:
    python -m scripts.generate_vrf_rolls --count 100
    python -m scripts.generate_vrf_rolls --count 100 --output data/rolls/vrf.csv
"""

import argparse

from dotenv import load_dotenv

from src.provably_fair_mechanisms.chainlink_vrf_mechanism import BetSwirlChainlinkMechanism

load_dotenv()

DEFAULT_OUTPUT = "data/rolls/chainlink_vrf_rolls.csv"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100, help="Number of rolls to generate.")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output CSV path.")
    args = parser.parse_args()

    mechanism = ChainlinkVRFMechanism(output_file=args.output)
    rolls = mechanism.generate_rolls(quantity=args.count)
    print(f"Done. {len(rolls)} rolls written to {args.output}")


if __name__ == "__main__":
    main()
