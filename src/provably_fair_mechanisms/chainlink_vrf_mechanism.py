import os
import time
from datetime import datetime, timezone
from typing import Any, List

import pandas as pd
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError

from src.config.configs import (
    MAX_VALUE,
    REJECTION_THRESHOLD,
    VRF_COORDINATOR_DEPLOY_BLOCK,
)
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
        "inputs": [{"name": "enableNativePayment", "type": "bool"}],
        "outputs": [{"name": "requestId", "type": "uint256"}],
    },
    {
        "name": "lastRequestId",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
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

COORDINATOR_ABI = [
    {
        # Emitted when a VRF request is made; contains the preseed and keyHash
        # needed to verify the request originated from the coordinator.
        "name": "RandomWordsRequested",
        "type": "event",
        "inputs": [
            {"name": "keyHash", "type": "bytes32", "indexed": True},
            {"name": "requestId", "type": "uint256", "indexed": False},
            {"name": "preSeed", "type": "uint256", "indexed": False},
            {"name": "subId", "type": "uint256", "indexed": True},
            {"name": "minimumRequestConfirmations", "type": "uint16", "indexed": False},
            {"name": "callbackGasLimit", "type": "uint32", "indexed": False},
            {"name": "numWords", "type": "uint32", "indexed": False},
            {"name": "extraArgs", "type": "bytes", "indexed": False},
            {"name": "sender", "type": "address", "indexed": True},
        ],
    },
    {
        # Emitted when the oracle fulfils a request; the fulfilment block must
        # be strictly after the request block to prove the output was unforeseeable.
        "name": "RandomWordsFulfilled",
        "type": "event",
        "inputs": [
            {"name": "requestId", "type": "uint256", "indexed": True},
            {"name": "outputSeed", "type": "uint256", "indexed": False},
            {"name": "subId", "type": "uint256", "indexed": True},
            {"name": "payment", "type": "uint96", "indexed": False},
            {"name": "nativePayment", "type": "bool", "indexed": False},
            {"name": "success", "type": "bool", "indexed": False},
            {"name": "onlyPremium", "type": "bool", "indexed": False},
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

        self._consumer = self._w3.eth.contract(
            address=Web3.to_checksum_address(self._consumer_address),
            abi=CONSUMER_ABI,
        )
        self._coordinator = self._w3.eth.contract(
            address=Web3.to_checksum_address(self._coordinator_address),
            abi=COORDINATOR_ABI,
        )

    def __str__(self) -> str:
        return "Chainlink VRF v2.5 Mechanism"

    # ======================== RANDOMNESS OPERATIONS ========================

    def _submit_request(self) -> int:
        tx_nonce = self._w3.eth.get_transaction_count(self._sender_address, "pending")
        tx = self._consumer.functions.requestRandomWords(False).build_transaction(
            {
                "from": self._sender_address,
                "nonce": tx_nonce,
                "gas": 200_000,
                "gasPrice": self._w3.eth.gas_price,
            }
        )
        signed = self._w3.eth.account.sign_transaction(
            tx, private_key=self._private_key
        )
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt["status"] != 1:
            raise ContractLogicError(
                f"requestRandomWords() reverted. tx={tx_hash.hex()}. "
                "Check subscription balance and consumer registration."
            )

        request_id = self._consumer.functions.lastRequestId().call()
        self._logger.info(f"Request submitted: requestId={request_id}")
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

            self._logger.debug(
                f"requestId={request_id} pending, retrying in {poll_interval}s..."
            )
            time.sleep(poll_interval)

        raise TimeoutError(
            f"requestId={request_id} not fulfilled within {max_wait}s. "
            "Check your subscription balance at vrf.chain.link."
        )

    def generate_rolls(
        self, quantity: int, save_rolls: bool = True
    ) -> List[RollRecord]:
        self._logger.info(f"Coordinator (server_seed): {self._coordinator_address}")
        self._logger.info(f"Consumer (client_seed): {self._consumer_address}")

        rolls: List[RollRecord] = []
        records = []

        for i in range(quantity):
            self._logger.info(f"Roll {i + 1}/{quantity}...")

            request_id = self._submit_request()
            raw_word = self._wait_for_fulfilment(request_id)
            raw_output = raw_word.to_bytes(32, "big")

            outcome = rejection_sampling(
                raw_output=raw_output,
                rejection_threshold=REJECTION_THRESHOLD,
                max_value=MAX_VALUE,
            )

            timestamp = datetime.now(timezone.utc)

            records.append(
                {
                    "server_seed": self._coordinator_address,
                    "client_seed": self._consumer_address,
                    "nonce": request_id,
                    "raw_output": raw_output.hex(),
                    "outcome": outcome,
                    "timestamp": timestamp.isoformat(),
                    "mechanism_id": self.MECHANISM_ID,
                }
            )

            rolls.append(
                RollRecord(
                    server_seed=self._coordinator_address,
                    client_seed=self._consumer_address,
                    nonce=request_id,
                    raw_output=raw_output,
                    outcome=outcome,
                    timestamp=timestamp,
                    mechanism_id=self.MECHANISM_ID,
                )
            )

            self._logger.info(f"requestId={request_id} -> outcome={outcome}")

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
        """
        Verifies a VRF roll by querying on-chain coordinator events for the
        given requestId (record.nonce) and confirming three properties:
        1. The requestId was assigned by the coordinator, not an EOA.
        2. A RandomWordsFulfilled event exists for the requestId.
        3. The fulfilment block is strictly after the request block.

        The recomputed outcome is derived from the stored raw_output, which the
        coordinator produced; if the raw_output itself is untampered the outcome
        will match.
        """
        request_id = record.nonce

        # Fetch the RandomWordsRequested event for this requestId.
        requested_events = self._coordinator.events.RandomWordsRequested.get_logs(
            argument_filters={"requestId": request_id},
            fromBlock=VRF_COORDINATOR_DEPLOY_BLOCK,
        )
        if not requested_events:
            return VerificationResult(
                record=record,
                disclosed_server_seed=self._coordinator_address,
                recomputed_outcome=-1,
                match=False,
            )
        request_block = requested_events[0]["blockNumber"]

        # Fetch the RandomWordsFulfilled event for this requestId.
        fulfilled_events = self._coordinator.events.RandomWordsFulfilled.get_logs(
            argument_filters={"requestId": request_id},
            fromBlock=request_block,
        )
        if not fulfilled_events:
            return VerificationResult(
                record=record,
                disclosed_server_seed=self._coordinator_address,
                recomputed_outcome=-1,
                match=False,
            )
        fulfilment_block = fulfilled_events[0]["blockNumber"]

        # Fulfilment must be strictly after the request to guarantee the oracle
        # could not have known the output at request time.
        if fulfilment_block <= request_block:
            return VerificationResult(
                record=record,
                disclosed_server_seed=self._coordinator_address,
                recomputed_outcome=-1,
                match=False,
            )

        # Recompute the outcome from the stored raw_output bytes.
        recomputed_outcome = rejection_sampling(
            raw_output=record.raw_output,
            rejection_threshold=REJECTION_THRESHOLD,
            max_value=MAX_VALUE,
        )

        recorded_str = f"{record.outcome:04d}"
        recomputed_str = f"{recomputed_outcome:04d}"
        is_match = self.safe_compare(recorded_str, recomputed_str)

        return VerificationResult(
            record=record,
            disclosed_server_seed="",
            recomputed_outcome=recomputed_outcome,
            match=is_match,
        )
