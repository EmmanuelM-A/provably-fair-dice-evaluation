"""
Generates N roll records using Chainlink VRF v2.5 and writes them to a
specified CSV file.

Required environment variables:
    VRF_RPC_URL             - Your Alchemy or Infura RPC endpoint
    VRF_CONSUMER_ADDRESS    - Address of your deployed consumer contract
    VRF_COORDINATOR_ADDRESS - Address of the VRF coordinator on the same network
    VRF_SENDER_ADDRESS      - The wallet address that pays for requests
    VRF_SENDER_PRIVATE_KEY  - Private key for that wallet (never hardcode this)
"""

import argparse
import os
import time
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError

from src.config.configs import MAX_VALUE, REJECTION_THRESHOLD
from src.logger.base_logger import BaseLogger
from src.utils.output_to_outcome_mapping import rejection_sampling

load_dotenv()

_logger = BaseLogger(__name__)

# ---------------------------------------------------------------------------
# ABI slices
# An ABI tells web3.py the shape of each function/event so it knows how to
# encode calls and decode responses. We only include what we need.
# ---------------------------------------------------------------------------

# The consumer contract is the one YOU deploy. It wraps the coordinator and
# exposes requestRandomWords() and getRequestStatus() to this script.
CONSUMER_ABI = [
    {
        # Submits a VRF randomness request to the coordinator.
        # Costs gas and changes on-chain state.
        "name": "requestRandomWords",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "enableNativePayment", "type": "bool"}],
        "outputs": [{"name": "requestId", "type": "uint256"}],
    },
    {
        # Returns the requestId of the most recent request.
        # Free to call — does not change state.
        "name": "lastRequestId",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        # Returns the fulfilment status and random words for a given requestId.
        # Free to call — does not change state.
        "name": "getRequestStatus",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_requestId", "type": "uint256"}],
        "outputs": [
            {"name": "fulfilled", "type": "bool"},
            {"name": "randomWords", "type": "uint256[]"},
        ],
    },
]


# =========================== on-chain helpers ===========================


def submit_request(w3: Web3, consumer, sender_address: str, private_key: str) -> int:
    # get_transaction_count returns the next unused nonce for this wallet.
    # "pending" includes unmined transactions so we never reuse a nonce.
    tx_nonce = w3.eth.get_transaction_count(sender_address, "pending")

    # build_transaction constructs the raw transaction dict but does not send it.
    # enableNativePayment=False means pay in LINK rather than ETH.
    tx = consumer.functions.requestRandomWords(False).build_transaction({
        "from": sender_address,
        "nonce": tx_nonce,
        "gas": 200_000,
        "gasPrice": w3.eth.gas_price,
    })

    # sign_transaction adds the sender's signature locally.
    # The private key never leaves this machine.
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)

    # send_raw_transaction broadcasts the signed transaction to the network.
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    # wait_for_transaction_receipt blocks until the transaction is mined.
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        raise ContractLogicError(
            f"requestRandomWords() reverted. tx={tx_hash.hex()}. "
            "Check subscription balance and consumer registration."
        )

    # Read the requestId from contract state rather than decoding event logs.
    # The consumer contract stores it as a public variable after each request.
    request_id = consumer.functions.lastRequestId().call()
    _logger.info(f"Request submitted: requestId={request_id}")
    return request_id


def wait_for_fulfilment(
    consumer,
    request_id: int,
    poll_interval: int = 5,
    max_wait: int = 600,
) -> int:
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        # getRequestStatus is a view function — free to call, no gas.
        # Returns (fulfilled: bool, randomWords: uint256[]).
        # "latest" bypasses HTTP RPC caching so we always read current chain state.
        fulfilled, random_words = consumer.functions.getRequestStatus(request_id).call(
            block_identifier="latest"
        )

        if fulfilled and random_words:
            _logger.info(f"requestId={request_id} fulfilled.")
            # We only request one random word per roll, so we take index 0.
            return random_words[0]

        _logger.debug(
            f"requestId={request_id} pending, retrying in {poll_interval}s..."
        )
        time.sleep(poll_interval)

    raise TimeoutError(
        f"requestId={request_id} not fulfilled within {max_wait}s. "
        "Check your subscription balance at vrf.chain.link."
    )


# ================================== Main ==================================

"""
The dice rolls are generated via a Chainlink VRF-based system to simulate
how a developer/user would interact with this framework. In reality you would
simulate/interact with your own real PFD mechanism/system or your actual
game/application to generate or obtain the dice rolls.

For the purpose of this demo, the dice rolls generated are from a fictional
PFD mechanism used to generate provably fair dice rolls for a Backgammon game.

The seeds used for this fictional game are as such:
- server_seed is the coordinator address — fixed for the session.
- client_seed is the consumer address — fixed for the session.
- nonce is the requestId — assigned per roll by the coordinator.

Because both address values are fixed contract addresses, they do not rotate
between rolls or sessions. The per-roll uniqueness comes entirely from the
requestId assigned by the coordinator's internal counter.

Verification works by reading the RandomWordsRequested and
RandomWordsFulfilled events from the coordinator contract on-chain and
confirming three properties:
1. The requestId was assigned by the coordinator, not an EOA.
2. The preseed was derived from a registered keyHash and block state.
3. The fulfilment block is strictly after the request block.


Usage:
    python -m scripts.generate_vrf_rolls --count 10
"""

DEFAULT_OUTPUT = "data/rolls/chainlink_vrf_rolls.csv"
MECHANISM_ID = "chainlink-vrf-v2.5"


def main():
    # ============================ ARGUMENTS ============================

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of rolls to generate. Keep low on testnet (each request costs LINK).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT,
        help="Output file path. Use .csv extension.",
    )
    args = parser.parse_args()

    # ========================= Session setup =========================

    # Load config from environment variables.
    # Never put secrets in source code or commit them to version control.
    rpc_url = os.environ["VRF_RPC_URL"]
    consumer_address = os.environ["VRF_CONSUMER_ADDRESS"]
    coordinator_address = os.environ["VRF_COORDINATOR_ADDRESS"]
    sender_address = os.environ["VRF_SENDER_ADDRESS"]
    private_key = os.environ["VRF_SENDER_PRIVATE_KEY"]

    # Web3 is the Python library for talking to an Ethereum node.
    # HTTPProvider wraps the RPC endpoint (your Alchemy or Infura URL).
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")

    # w3.eth.contract binds a Python object to a deployed contract.
    # The ABI tells it how to encode calls and decode responses.
    consumer = w3.eth.contract(
        address=Web3.to_checksum_address(consumer_address),
        abi=CONSUMER_ABI,
    )

    # server_seed and client_seed are fixed for the session.
    # They are contract addresses, not rotating secrets.
    _logger.info(f"Coordinator (server_seed): {coordinator_address}")
    _logger.info(f"Consumer (client_seed): {consumer_address}")

    # ======================== Roll generation ========================

    records = []

    for i in range(args.count):
        _logger.info(f"Roll {i + 1}/{args.count}...")

        # Submit the VRF request and wait for the oracle to fulfil it.
        # Each call costs LINK from the subscription — keep count low on testnet.
        request_id = submit_request(w3, consumer, sender_address, private_key)
        raw_word = wait_for_fulfilment(consumer, request_id)

        # Convert the 256-bit integer to 32 bytes for storage and sampling.
        raw_output = raw_word.to_bytes(32, "big")

        outcome = rejection_sampling(
            raw_output=raw_output,
            rejection_threshold=REJECTION_THRESHOLD,
            max_value=MAX_VALUE,
        )

        records.append({
            # coordinator address — the on-chain authority, fixed per session.
            "server_seed": coordinator_address,
            # consumer address — the requesting contract, fixed per session.
            "client_seed": consumer_address,
            # requestId — assigned by the coordinator per roll, not by us.
            "nonce": request_id,
            # raw_output stored as hex so it survives CSV round-trips.
            "raw_output": raw_output.hex(),
            "outcome": outcome,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mechanism_id": MECHANISM_ID,
        })

        _logger.info(f"requestId={request_id} -> outcome={outcome}")

    # ========================== Write output ==========================

    df = pd.DataFrame(records)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)

    _logger.info(f"Done. {len(df)} rolls written to {args.output}")
    _logger.info(f"\n{df.head()}")


if __name__ == "__main__":
    main()