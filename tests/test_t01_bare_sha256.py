"""
T-1: Bare SHA-256 Concatenation Detection

A mechanism using SHA-256(server_seed || client_seed || nonce) instead of
HMAC-SHA256 produces statistically uniform output, so all automated Light
checks pass. The protocol-level flaw is captured in the NPER assessment
(bareSHA256Check: False) and must appear in the generated report.
"""
import hashlib
import math
import os
from datetime import datetime, timezone
from typing import List

import pytest

from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.enigines.pfd import ProvablyFairDiceMechanism
from src.enigines.report import ReportEngine
from src.provably_fair_mechanisms.hmac_mechanism import StakesHMACMechanism
from src.utils.types import RollRecord, VerificationResult

_MAX_ROLL = 10001


class BareSHA256Mechanism(ProvablyFairDiceMechanism):
    """Uses SHA-256(server_seed + client_seed + nonce) — no HMAC key separation."""

    def __init__(self, output_file: str) -> None:
        self.server_seed = os.urandom(32).hex()
        self.client_seed = "test-client-seed"
        self.MECHANISM_ID = "sha256-concat"
        self._output_file = output_file

    def __str__(self) -> str:
        return "Bare SHA-256 Concat Mechanism"

    def _raw(self, server_seed: str, client_seed: str, nonce: int) -> bytes:
        return hashlib.sha256(f"{server_seed}{client_seed}{nonce}".encode()).digest()

    def _outcome(self, raw: bytes) -> float:
        total = sum(raw[i] / (256 ** (i + 1)) for i in range(4))
        return math.floor(total * _MAX_ROLL) / 100

    def generate_rolls(self, quantity: int, save_rolls: bool = False) -> List[RollRecord]:
        rolls = []
        for nonce in range(1, quantity + 1):
            raw = self._raw(self.server_seed, self.client_seed, nonce)
            rolls.append(RollRecord(
                server_seed=self.server_seed,
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


def test_bare_sha256_statistical_checks_pass_but_nper_flags_failure(tmp_path):
    config = EvaluationConfig(
        n_faces=100,
        server_seed_min_entropy_threshold_bits=0.0,
        n_latency_requests=20,
    )
    mechanism = BareSHA256Mechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    from src.provably_fair_mechanisms.hmac_mechanism import stake_dice_outcome
    result = engine.run_evaluation(rolls, "LIGHT", mapping_fn=stake_dice_outcome)

    assert result.randomness.light.sanity_check.passed
    assert result.security.light.nonce_presence.passed
    assert result.halted_at is None

    nper = {"bareSHA256Check": False, "csprngCompliance": True}
    report_engine = ReportEngine(str(tmp_path / "report.html"), n_faces=100)
    report_path = report_engine.generate(result, rolls, "LIGHT", non_programmable=nper)

    assert os.path.exists(report_path)
    content = open(report_path, encoding="utf-8").read()
    assert len(content) > 100
