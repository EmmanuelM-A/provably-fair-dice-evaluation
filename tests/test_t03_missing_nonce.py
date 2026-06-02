"""
T-3: Missing Nonce Detection

A mechanism that generates nonce=0 for every roll fails the nonce_presence
check at Light tier. The evaluation engine must halt at LIGHT and not proceed
to IN_DEPTH.
"""
import hashlib
import hmac as hmac_lib
import math
import os
from datetime import datetime, timezone
from typing import List

from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.provably_fair_mechanisms.hmac_mechanism import stake_dice_outcome
from src.utils.types import RollRecord, VerificationResult

_MAX_ROLL = 10001


class NoNonceMechanism(ProvablyFairDiceMechanism):
    """HMAC-SHA256 mechanism that omits nonces — always stores nonce=0."""

    def __init__(self, output_file: str) -> None:
        self.server_seed = os.urandom(32).hex()
        self.client_seed = "test-client-seed"
        self.MECHANISM_ID = "hmac-sha256-no-nonce"
        self._output_file = output_file

    def __str__(self) -> str:
        return "No-Nonce HMAC Mechanism"

    def _raw(self, server_seed: str, client_seed: str, cursor: int) -> bytes:
        msg = f"{client_seed}:{cursor}:0".encode()
        return hmac_lib.new(server_seed.encode(), msg, digestmod=hashlib.sha256).digest()

    def _outcome(self, raw: bytes) -> float:
        total = sum(raw[i] / (256 ** (i + 1)) for i in range(4))
        return math.floor(total * _MAX_ROLL) / 100

    def generate_rolls(self, quantity: int, save_rolls: bool = False) -> List[RollRecord]:
        rolls = []
        for cursor in range(quantity):
            raw = self._raw(self.server_seed, self.client_seed, cursor)
            rolls.append(RollRecord(
                server_seed=self.server_seed,
                client_seed=self.client_seed,
                nonce=0,
                raw_output=raw,
                outcome=self._outcome(raw),
                timestamp=datetime.now(timezone.utc),
                mechanism_id=self.MECHANISM_ID,
            ))
        return rolls

    def verify(self, record: RollRecord) -> VerificationResult:
        raw = self._raw(record.server_seed, record.client_seed, 0)
        recomputed = self._outcome(raw)
        return VerificationResult(
            record=record,
            disclosed_server_seed=record.server_seed,
            recomputed_outcome=recomputed,
            match=self.safe_compare(f"{recomputed:.2f}", f"{record.outcome:.2f}"),
        )


def test_missing_nonce_halts_at_light_tier(tmp_path):
    config = EvaluationConfig(
        n_faces=100,
        server_seed_min_entropy_threshold_bits=0.0,
        n_latency_requests=20,
    )
    mechanism = NoNonceMechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    result = engine.run_evaluation(rolls, "IN_DEPTH", mapping_fn=stake_dice_outcome)

    assert not result.security.light.nonce_presence.passed
    assert result.halted_at == "LIGHT"
    assert result.randomness.in_depth is None
