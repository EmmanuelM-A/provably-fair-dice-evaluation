import hashlib
import hmac as _hmac
import os
import time
from datetime import datetime, timezone
from typing import List

import pandas as pd
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.types import Wei

from src.config.configs import MAX_VALUE, REJECTION_THRESHOLD
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.logger.base_logger import BaseLogger
from src.utils.common_operations import rejection_sampling
from src.utils.types import RollRecord, VerificationResult

load_dotenv()

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


class ChainlinkVRFMechanism(ProvablyFairDiceMechanism):

    # ========================= MECHANISM SPECIFIC =========================

    def __init__(self, output_file: str) -> None:
        self.MECHANISM_ID = "chainlink-vrf-v2.5"
        self._logger = BaseLogger(__name__)
        self._output_file = output_file

        rpc_url = os.environ["VRF_RPC_URL"]
        self._consumer_address = os.environ["VRF_CONSUMER_ADDRESS"]
        self._coordinator_address = os.environ["VRF_COORDINATOR_ADDRESS"]
        self._sender_address = os.environ["VRF_SENDER_ADDRESS"]
        self._private_key = os.environ["VRF_SENDER_PRIVATE_KEY"]

        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self._w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")

        for label, addr in [
            ("VRF_CONSUMER_ADDRESS", self._consumer_address),
            ("VRF_COORDINATOR_ADDRESS", self._coordinator_address),
        ]:
            code = self._w3.eth.get_code(Web3.to_checksum_address(addr))
            if code in (b"", b"0x"):
                raise ValueError(
                    f"No contract deployed at {label}={addr}. "
                    "Check your .env — the address may be a wallet or a wrong network."
                )

        self._consumer = self._w3.eth.contract(
            address=Web3.to_checksum_address(self._consumer_address),
            abi=CONSUMER_ABI,
        )

    def __str__(self) -> str:
        return "Chainlink VRF v2.5 Mechanism"

    # ======================== RANDOMNESS OPERATIONS ========================

    def _submit_request(self) -> int:
        tx_nonce = self._w3.eth.get_transaction_count(
            Web3.to_checksum_address(self._sender_address), "pending"
        )
        base_fee = Wei(self._w3.eth.get_block("latest")["baseFeePerGas"])  # type: ignore[index]
        priority_fee = Wei(2_000_000_000)  # 2 gwei
        max_fee = Wei(base_fee * 2 + priority_fee)

        tx = self._consumer.functions.requestRandomWords(False, 1).build_transaction(
            {
                "from": self._sender_address,  # type: ignore[arg-type]
                "nonce": tx_nonce,
                "gas": 250_000,
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": priority_fee,
            }
        )
        signed = self._w3.eth.account.sign_transaction(tx, private_key=self._private_key)
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        self._logger.info(f"VRF request sent: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt["status"] != 1:
            raise ContractLogicError(
                f"requestRandomWords() reverted. tx={tx_hash.hex()}. "
                "Check subscription balance and consumer registration."
            )

        # requestId is the first non-indexed field in the coordinator's
        # RandomWordsRequested event — always the first 32 bytes of log data.
        coordinator_address = Web3.to_checksum_address(self._coordinator_address)
        request_id = None
        for log in receipt["logs"]:
            if Web3.to_checksum_address(log["address"]) == coordinator_address:
                request_id = int.from_bytes(bytes(log["data"][:32]), "big")
                break

        if request_id is None:
            raise RuntimeError(
                f"No coordinator log in receipt. tx={tx_hash.hex()}. "
                f"Logs from addresses: {[log['address'] for log in receipt['logs']]}"
            )
        self._logger.info(f"VRF requestId={request_id}")
        return request_id

    def _wait_for_fulfilment(
        self,
        request_id: int,
        poll_interval: int = 5,
        max_wait: int = 600,
    ) -> int:
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            fulfilled, random_words = self._consumer.functions.getRequestStatus(
                request_id
            ).call(block_identifier="latest")

            if fulfilled and random_words:
                self._logger.info(f"requestId={request_id} fulfilled.")
                return random_words[0]

            self._logger.debug(f"requestId={request_id} pending, retrying in {poll_interval}s...")
            time.sleep(poll_interval)

        raise TimeoutError(
            f"requestId={request_id} not fulfilled within {max_wait}s. "
            "Check your subscription balance at vrf.chain.link."
        )

    def generate_rolls(self, quantity: int, save_rolls: bool = True) -> List[RollRecord]:
        # 1. Mine one VRF word — this becomes the server seed for the session.
        request_id = self._submit_request()
        vrf_word = self._wait_for_fulfilment(request_id)
        server_seed_bytes = vrf_word.to_bytes(32, "big")
        server_seed = server_seed_bytes.hex()
        client_seed = self._consumer_address
        timestamp = datetime.now(timezone.utc)

        self._logger.info(f"Session server_seed={server_seed} (VRF requestId={request_id})")

        # 2. Derive all rolls via HMAC-SHA256 — no further on-chain calls.
        rolls: List[RollRecord] = []
        records = []
        for nonce in range(quantity):
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
                    "mechanism_id": self.MECHANISM_ID,
                }
            )
            rolls.append(
                RollRecord(
                    server_seed=server_seed,
                    client_seed=client_seed,
                    nonce=nonce,
                    raw_output=raw_output,
                    outcome=outcome,
                    timestamp=timestamp,
                    mechanism_id=self.MECHANISM_ID,
                )
            )

        df = pd.DataFrame(records)
        if save_rolls:
            os.makedirs(os.path.dirname(self._output_file), exist_ok=True)
            df.to_csv(self._output_file, index=False)
            self._logger.info(f"Done. {len(df)} rolls written to {self._output_file}")
        else:
            self._logger.info(f"Done. {len(df)} rolls generated (not saved).")

        return rolls

    # ======================= VERIFICATION OPERATIONS =======================

    def verify(self, record: RollRecord) -> VerificationResult:
        # Recompute HMAC from the stored server_seed, client_seed, and nonce.
        server_seed_bytes = bytes.fromhex(record.server_seed)
        raw_output = _hmac.new(
            key=server_seed_bytes,
            msg=f"{record.client_seed}{record.nonce}".encode(),
            digestmod=hashlib.sha256,
        ).digest()
        recomputed_outcome = rejection_sampling(
            raw_output=raw_output,
            rejection_threshold=REJECTION_THRESHOLD,
            max_value=MAX_VALUE,
        )
        is_match = self.safe_compare(
            f"{record.outcome:04d}", f"{recomputed_outcome:04d}"
        )
        return VerificationResult(
            record=record,
            disclosed_server_seed=record.server_seed,
            recomputed_outcome=recomputed_outcome,
            match=is_match,
        )
