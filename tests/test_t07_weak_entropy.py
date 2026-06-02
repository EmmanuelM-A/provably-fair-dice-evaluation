"""
T-7: Weak Entropy Source Detection

A mechanism that derives each roll's server seed from the current Unix timestamp
(truncated to seconds) will produce a single unique seed across all rolls
generated within the same second. The server_seed_min_entropy check at Light
tier detects this and flags the failure, while the HMAC structure itself is
valid so the sanity check passes.
"""
import hashlib
import hmac as hmac_lib
import math
import time
from datetime import datetime, timezone
from typing import List

from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.provably_fair_mechanisms.hmac_mechanism import stake_dice_outcome
from src.utils.types import RollRecord, VerificationResult

_MAX_ROLL = 10001


class TimestampSeedMechanism(ProvablyFairDiceMechanism):
    """HMAC-SHA256 mechanism that generates a new server seed per roll from timestamp."""

    def __init__(self, output_file: str) -> None:
        self.client_seed = "test-client-seed"
        self.MECHANISM_ID = "hmac-sha256-timestamp"
        self._output_file = output_file

    def __str__(self) -> str:
        return "Timestamp-Seeded HMAC Mechanism"

    def _server_seed_from_timestamp(self) -> str:
        return str(int(time.time()))

    def _raw(self, server_seed: str, client_seed: str, nonce: int) -> bytes:
        msg = f"{client_seed}:{nonce}:0".encode()
        return hmac_lib.new(server_seed.encode(), msg, digestmod=hashlib.sha256).digest()

    def _outcome(self, raw: bytes) -> float:
        total = sum(raw[i] / (256 ** (i + 1)) for i in range(4))
        return math.floor(total * _MAX_ROLL) / 100

    def generate_rolls(self, quantity: int, save_rolls: bool = False) -> List[RollRecord]:
        rolls = []
        for nonce in range(1, quantity + 1):
            server_seed = self._server_seed_from_timestamp()
            raw = self._raw(server_seed, self.client_seed, nonce)
            rolls.append(RollRecord(
                server_seed=server_seed,
                client_seed=self.client_seed,
                nonce=nonce,
                raw_output=raw,
                outcome=self._outcome(raw),
                timestamp=datetime.now(timezone.utc),
                mechanism_id=self.MECHANISM_ID,
            ))
        return rolls

    def verify(self, record: RollRecord) -> VerificationResult:
        raw = self._raw(record.server_seed, record.client_seed, record.nonce)
        recomputed = self._outcome(raw)
        return VerificationResult(
            record=record,
            disclosed_server_seed=record.server_seed,
            recomputed_outcome=recomputed,
            match=self.safe_compare(f"{recomputed:.2f}", f"{record.outcome:.2f}"),
        )


def test_timestamp_seed_fails_entropy_check_at_light_tier(tmp_path):
    config = EvaluationConfig(
        n_faces=100,
        server_seed_min_entropy_threshold_bits=1.0,
        n_latency_requests=20,
    )
    mechanism = TimestampSeedMechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    result = engine.run_evaluation(rolls, "LIGHT", mapping_fn=stake_dice_outcome)

    assert not result.randomness.light.server_seed_min_entropy.passed

    assert result.randomness.light.sanity_check.passed
    assert result.security.light.nonce_presence.passed
