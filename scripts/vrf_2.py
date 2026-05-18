"""
Chainlink VRF v2.5 — clean standalone roll generator.

Architecture:
  1. Submit ONE VRF request for a single random word (one on-chain transaction).
  2. Use that word as the session server_seed.
  3. Derive all N rolls via HMAC-SHA256(server_seed, consumer_address + nonce).
  4. Write results to CSV.

Required .env variables:
  VRF_RPC_URL             - Alchemy/Infura Sepolia endpoint
                            (must be "Injected Provider" network in Remix when deploying)
  VRF_CONSUMER_ADDRESS    - Address of your VRFConsumer contract deployed on Sepolia
  VRF_COORDINATOR_ADDRESS - 0x9DdfaCa8183c41ad55329BdeeD9F6A8d53168B1B  (Sepolia VRF v2.5)
  VRF_SENDER_ADDRESS      - Wallet address that owns the subscription
  VRF_SENDER_PRIVATE_KEY  - Private key for that wallet

Usage:
  python -m scripts.vrf_2 --count 1000
  python -m scripts.vrf_2 --count 1000 --output data/rolls/vrf.csv
"""

import argparse
import hashlib
import hmac as _hmac
import os
import time
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.types import Wei

from src.config.configs import MAX_VALUE, REJECTION_THRESHOLD
from src.logger.base_logger import BaseLogger
from src.utils.common_operations import rejection_sampling

load_dotenv()

_logger = BaseLogger(__name__)

SEPOLIA_CHAIN_ID = 11155111

CONSUMER_ABI = [
    {
        "name": "requestRandomWords",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "enableNativePayment", "type": "bool"},
            {"name": "numWords", "type": "uint32"},
        ],
        "outputs": [{"name": "requestId", "type": "uint256"}],
    },
    {
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


# ──────────────────────────────────────────────────────────────────────────────
# On-chain helpers
# ──────────────────────────────────────────────────────────────────────────────

def _connect() -> tuple:
    rpc_url = os.environ["VRF_RPC_URL"]
    consumer_addr = os.environ["VRF_CONSUMER_ADDRESS"]
    coordinator_addr = os.environ["VRF_COORDINATOR_ADDRESS"]
    sender_addr = os.environ["VRF_SENDER_ADDRESS"]
    private_key = os.environ["VRF_SENDER_PRIVATE_KEY"]

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")

    chain_id = w3.eth.chain_id
    if chain_id != SEPOLIA_CHAIN_ID:
        raise ConnectionError(
            f"Wrong network: expected Sepolia (chainId=11155111), got chainId={chain_id}. "
            "Check VRF_RPC_URL."
        )
    _logger.info(f"Connected to Sepolia via {rpc_url}")

    for label, addr in [("VRF_CONSUMER_ADDRESS", consumer_addr), ("VRF_COORDINATOR_ADDRESS", coordinator_addr)]:
        code = w3.eth.get_code(Web3.to_checksum_address(addr))
        if code in (b"", b"0x"):
            raise ValueError(
                f"No contract at {label}={addr}.\n"
                "If you deployed via Remix, make sure:\n"
                "  • Environment = 'Injected Provider - MetaMask'\n"
                "  • MetaMask is on the Sepolia network\n"
                "Then redeploy and update your .env."
            )

    consumer = w3.eth.contract(
        address=Web3.to_checksum_address(consumer_addr),
        abi=CONSUMER_ABI,
    )
    return w3, consumer, consumer_addr, coordinator_addr, sender_addr, private_key


def _submit_request(w3: Web3, consumer, coordinator_addr: str, sender_addr: str, private_key: str) -> int:
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(sender_addr), "pending")
    base_fee = Wei(w3.eth.get_block("latest")["baseFeePerGas"])  # type: ignore[index]
    priority_fee = Wei(2_000_000_000)  # 2 gwei tip
    max_fee = Wei(base_fee * 2 + priority_fee)

    tx = consumer.functions.requestRandomWords(False, 1).build_transaction(
        {
            "from": sender_addr,  # type: ignore[arg-type]
            "nonce": nonce,
            "gas": 250_000,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    _logger.info(f"TX sent → https://sepolia.etherscan.io/tx/{tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    if receipt["status"] != 1:
        raise ContractLogicError(
            f"requestRandomWords() reverted (tx={tx_hash.hex()}). "
            "Check subscription balance and that this consumer is registered."
        )

    # requestId is the first non-indexed field of the coordinator's
    # RandomWordsRequested event → always the first 32 bytes of log data.
    coordinator_cs = Web3.to_checksum_address(coordinator_addr)
    for log in receipt["logs"]:
        if Web3.to_checksum_address(log["address"]) == coordinator_cs:
            request_id = int.from_bytes(bytes(log["data"][:32]), "big")
            _logger.info(f"VRF requestId={request_id}")
            return request_id

    raise RuntimeError(
        f"Coordinator log not found in receipt (tx={tx_hash.hex()}). "
        f"Logs came from: {[log['address'] for log in receipt['logs']]}. "
        f"Expected coordinator at {coordinator_addr}."
    )


def _wait_for_fulfilment(consumer, request_id: int, poll_interval: int = 5, max_wait: int = 600) -> int:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        fulfilled, random_words = consumer.functions.getRequestStatus(request_id).call(
            block_identifier="latest"
        )
        if fulfilled and random_words:
            _logger.info(f"requestId={request_id} fulfilled.")
            return random_words[0]
        _logger.debug(f"requestId={request_id} pending — retrying in {poll_interval}s...")
        time.sleep(poll_interval)

    raise TimeoutError(
        f"requestId={request_id} not fulfilled within {max_wait}s. "
        "Check your subscription balance at vrf.chain.link/sepolia."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT = "data/rolls/chainlink_vrf_rolls.csv"
MECHANISM_ID = "chainlink-vrf-v2.5"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100, help="Number of rolls to generate.")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output CSV path.")
    args = parser.parse_args()

    w3, consumer, consumer_addr, coordinator_addr, sender_addr, private_key = _connect()

    # ── Step 1: one on-chain VRF request ────────────────────────────────────
    request_id = _submit_request(w3, consumer, coordinator_addr, sender_addr, private_key)
    vrf_word = _wait_for_fulfilment(consumer, request_id)

    server_seed_bytes = vrf_word.to_bytes(32, "big")
    server_seed = server_seed_bytes.hex()
    client_seed = consumer_addr
    timestamp = datetime.now(timezone.utc)

    _logger.info(f"server_seed = {server_seed}  (VRF requestId={request_id})")

    # ── Step 2: derive all rolls locally via HMAC ────────────────────────────
    records = []
    for nonce in range(args.count):
        raw_output = _hmac.new(
            key=server_seed_bytes,
            msg=f"{client_seed}{nonce}".encode(),
            digestmod=hashlib.sha256,
        ).digest()
        outcome = rejection_sampling(
            raw_output=raw_output,
            rejection_threshold=REJECTION_THRESHOLD,
            max_value=MAX_VALUE,
        )
        records.append(
            {
                "server_seed": server_seed,
                "client_seed": client_seed,
                "nonce": nonce,
                "raw_output": raw_output.hex(),
                "outcome": outcome,
                "timestamp": timestamp.isoformat(),
                "mechanism_id": MECHANISM_ID,
            }
        )

    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)
    _logger.info(f"Done. {len(df)} rolls written to {args.output}")
    _logger.info(f"\n{df.head()}")


if __name__ == "__main__":
    main()
