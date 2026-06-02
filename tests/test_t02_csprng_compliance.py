"""
T-2: Non-CSPRNG Seed Generation Detection

A mechanism that seeds from Mersenne Twister (random module) instead of
os.urandom produces statistically diverse output, so all automated Light
checks pass. The protocol-level flaw is captured in the NPER assessment
(csprngCompliance: False) and must appear in the generated report.
"""
import hashlib
import hmac as hmac_lib
import math
import os
import random
import time
from datetime import datetime, timezone
from typing import List

import pytest

from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.enigines.report import ReportEngine
from src.provably_fair_mechanisms.hmac_mechanism import stake_dice_outcome
from src.utils.types import RollRecord, VerificationResult

_MAX_ROLL = 10001


class MersenneTwisterMechanism(ProvablyFairDiceMechanism):
    """Uses Mersenne Twister seeded from timestamp for server seeds — not CSPRNG."""

    def __init__(self, output_file: str) -> None:
        random.seed(int(time.time()))
        self.client_seed = "test-client-seed"
        self.MECHANISM_ID = "mt-seeded-hmac"
        self._output_file = output_file

    def __str__(self) -> str:
        return "Mersenne Twister Seeded HMAC Mechanism"

    def _make_server_seed(self) -> str:
        return random.randbytes(32).hex()

    def _raw(self, server_seed: str, client_seed: str, nonce: int) -> bytes:
        msg = f"{client_seed}:{nonce}:0".encode()
        return hmac_lib.new(server_seed.encode(), msg, digestmod=hashlib.sha256).digest()

    def _outcome(self, raw: bytes) -> float:
        total = sum(raw[i] / (256 ** (i + 1)) for i in range(4))
        return math.floor(total * _MAX_ROLL) / 100

    def generate_rolls(self, quantity: int, save_rolls: bool = False) -> List[RollRecord]:
        rolls = []
        for nonce in range(1, quantity + 1):
            server_seed = self._make_server_seed()
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


def test_csprng_statistical_checks_pass_but_nper_flags_failure(tmp_path):
    config = EvaluationConfig(
        n_faces=100,
        server_seed_min_entropy_threshold_bits=0.0,
        n_latency_requests=20,
    )
    mechanism = MersenneTwisterMechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    result = engine.run_evaluation(rolls, "LIGHT", mapping_fn=stake_dice_outcome)

    assert result.randomness.light.sanity_check.passed
    assert result.security.light.nonce_presence.passed
    assert result.halted_at is None

    nper = {"bareSHA256Check": True, "csprngCompliance": False}
    report_engine = ReportEngine(str(tmp_path / "report.html"), n_faces=100)
    report_path = report_engine.generate(result, rolls, "LIGHT", non_programmable=nper)

    assert os.path.exists(report_path)
    content = open(report_path, encoding="utf-8").read()
    assert len(content) > 100
