"""
Contains tests responsible for checking if mechanisms work correctly and
implement the methods as expected.
"""

import pytest
from datetime import datetime, timezone

from src.provably_fair_mechanisms.hmac_mechanism import ProvablyFairDiceHMACMechanism
from src.utils.provably_fair_mechanism import ProvablyFairDiceMechanism
from src.utils.types import RollRecord, VerificationResult

# ====================== Test fixtures and shared data ======================

"""
Predefined seed triples with known disclosed server seeds.
Each entry contains the inputs needed to generate a roll and the disclosed
server seed needed to verify it. The disclosed server seed is the plaintext
that was committed to before play via SHA-256(server_seed).
"""
PREDEFINED_RECORDS = [
    {
        "server_seed": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "client_seed": "player-seed-alpha",
        "nonce": "1",
        "disclosed_server_seed": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    },
    {
        "server_seed": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "client_seed": "player-seed-beta",
        "nonce": "42",
        "disclosed_server_seed": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    },
    {
        "server_seed": "0000000000000000000000000000000000000000000000000000000000000001",
        "client_seed": "player-seed-gamma",
        "nonce": "999",
        "disclosed_server_seed": "0000000000000000000000000000000000000000000000000000000000000001",
    },
    {
        # Same seeds, different nonce, so outcome must differ from record index 0
        "server_seed": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "client_seed": "player-seed-alpha",
        "nonce": "2",
        "disclosed_server_seed": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    },
    {
        # Same seeds and nonce as index 0, so outcome must match index 0 (deterministic)
        "server_seed": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "client_seed": "player-seed-alpha",
        "nonce": "1",
        "disclosed_server_seed": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    },
]

# Mechanisms under test. Add any new mechanism class here and all tests run
# against it automatically.
MECHANISMS = [
    ProvablyFairDiceHMACMechanism(),
]


def pytest_generate_tests(metafunc):
    if "mechanism" in metafunc.fixturenames:
        metafunc.parametrize(
            "mechanism", MECHANISMS, ids=[m.__class__.__name__ for m in MECHANISMS]
        )


# ============================= Helpers =============================


def generate_record(mechanism: ProvablyFairDiceMechanism, entry: dict) -> RollRecord:
    return mechanism.generate_roll(
        server_seed=entry["server_seed"],
        client_seed=entry["client_seed"],
        nonce=entry["nonce"],
    )


# ======================= RollRecord structure tests =======================


class TestRollRecordStructure:
    def test_record_has_all_required_fields(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)

        assert hasattr(record, "server_seed")
        assert hasattr(record, "client_seed")
        assert hasattr(record, "nonce")
        assert hasattr(record, "raw_output")
        assert hasattr(record, "outcome")
        assert hasattr(record, "timestamp")
        assert hasattr(record, "mechanism_id")

    def test_raw_output_is_bytes(self, mechanism):
        record = generate_record(mechanism, PREDEFINED_RECORDS[0])
        assert isinstance(record.raw_output, bytes)

    def test_raw_output_is_not_empty(self, mechanism):
        record = generate_record(mechanism, PREDEFINED_RECORDS[0])
        assert len(record.raw_output) > 0

    def test_outcome_is_integer(self, mechanism):
        record = generate_record(mechanism, PREDEFINED_RECORDS[0])
        assert isinstance(record.outcome, int)

    def test_timestamp_is_timezone_aware(self, mechanism):
        record = generate_record(mechanism, PREDEFINED_RECORDS[0])
        assert isinstance(record.timestamp, datetime)
        assert record.timestamp.tzinfo is not None

    def test_timestamp_is_utc(self, mechanism):
        record = generate_record(mechanism, PREDEFINED_RECORDS[0])
        assert record.timestamp.tzinfo == timezone.utc

    def test_mechanism_id_is_string(self, mechanism):
        record = generate_record(mechanism, PREDEFINED_RECORDS[0])
        assert isinstance(record.mechanism_id, str)
        assert len(record.mechanism_id) > 0

    def test_inputs_preserved_in_record(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)

        assert record.server_seed == entry["server_seed"]
        assert record.client_seed == entry["client_seed"]
        assert record.nonce == entry["nonce"]


# ---------------------------------------------------------------------------
# Outcome range tests
# ---------------------------------------------------------------------------


class TestOutcomeRange:

    @pytest.mark.parametrize("entry", PREDEFINED_RECORDS)
    def test_outcome_within_valid_range(self, mechanism, entry):
        record = generate_record(mechanism, entry)
        assert (
            0 <= record.outcome <= 9999
        ), f"Outcome {record.outcome} is outside the expected range [0, 9999]"

    def test_all_predefined_records_produce_valid_outcomes(self, mechanism):
        for entry in PREDEFINED_RECORDS:
            record = generate_record(mechanism, entry)
            assert 0 <= record.outcome <= 9999


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_inputs_produce_same_outcome(self, mechanism):
        # Records at index 0 and 4 share identical inputs.
        record_a = generate_record(mechanism, PREDEFINED_RECORDS[0])
        record_b = generate_record(mechanism, PREDEFINED_RECORDS[4])

        assert (
            record_a.outcome == record_b.outcome
        ), f"Same inputs produced different outcomes: {record_a.outcome} vs {record_b.outcome}"

    def test_same_inputs_produce_same_raw_output(self, mechanism):
        record_a = generate_record(mechanism, PREDEFINED_RECORDS[0])
        record_b = generate_record(mechanism, PREDEFINED_RECORDS[4])

        assert record_a.raw_output == record_b.raw_output

    def test_different_nonce_produces_different_outcome(self, mechanism):
        # Records at index 0 and 3 share seeds but differ in nonce.
        record_nonce_1 = generate_record(mechanism, PREDEFINED_RECORDS[0])
        record_nonce_2 = generate_record(mechanism, PREDEFINED_RECORDS[3])

        assert (
            record_nonce_1.raw_output != record_nonce_2.raw_output
        ), "Different nonces must produce different raw outputs"

    def test_different_client_seeds_produce_different_outcomes(self, mechanism):
        entry_a = PREDEFINED_RECORDS[0]
        entry_b = {**entry_a, "client_seed": "completely-different-client-seed"}

        record_a = generate_record(mechanism, entry_a)
        record_b = generate_record(mechanism, entry_b)

        assert record_a.raw_output != record_b.raw_output

    def test_different_server_seeds_produce_different_outcomes(self, mechanism):
        entry_a = PREDEFINED_RECORDS[0]
        entry_b = {**entry_a, "server_seed": "f" * 64}

        record_a = generate_record(mechanism, entry_a)
        record_b = generate_record(mechanism, entry_b)

        assert record_a.raw_output != record_b.raw_output


# ---------------------------------------------------------------------------
# Verification tests
# ---------------------------------------------------------------------------


class TestVerification:

    def test_correct_disclosed_seed_passes_verification(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, entry["disclosed_server_seed"])

        assert isinstance(result, VerificationResult)
        assert result.match is True

    @pytest.mark.parametrize("entry", PREDEFINED_RECORDS)
    def test_all_predefined_records_verify_correctly(self, mechanism, entry):
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, entry["disclosed_server_seed"])

        assert result.match is True, (
            f"Verification failed for nonce={entry['nonce']}, "
            f"recorded={record.outcome}, recomputed={result.recomputed_outcome}"
        )

    def test_wrong_disclosed_seed_fails_verification(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, "wrong-server-seed")

        assert result.match is False

    def test_tampered_outcome_fails_verification(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)

        tampered_outcome = (record.outcome + 1) % 10_000
        tampered_record = RollRecord(
            server_seed=record.server_seed,
            client_seed=record.client_seed,
            nonce=record.nonce,
            raw_output=record.raw_output,
            outcome=tampered_outcome,
            timestamp=record.timestamp,
            mechanism_id=record.mechanism_id,
        )

        result = mechanism.verify(tampered_record, entry["disclosed_server_seed"])
        assert result.match is False

    def test_verification_result_contains_recomputed_outcome(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, entry["disclosed_server_seed"])

        assert hasattr(result, "recomputed_outcome")
        assert isinstance(result.recomputed_outcome, int)

    def test_recomputed_outcome_matches_recorded_on_valid_verification(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, entry["disclosed_server_seed"])

        assert result.recomputed_outcome == record.outcome

    def test_verification_result_contains_disclosed_seed(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, entry["disclosed_server_seed"])

        assert result.disclosed_server_seed == entry["disclosed_server_seed"]

    def test_verification_result_contains_original_record(self, mechanism):
        entry = PREDEFINED_RECORDS[0]
        record = generate_record(mechanism, entry)
        result = mechanism.verify(record, entry["disclosed_server_seed"])

        assert result.record is record


# ---------------------------------------------------------------------------
# Commitment tests
# ---------------------------------------------------------------------------


class TestCommitment:

    def test_commit_returns_string(self, mechanism):
        commitment = mechanism.commit(PREDEFINED_RECORDS[0]["server_seed"])
        assert isinstance(commitment, str)

    def test_commit_is_deterministic(self, mechanism):
        seed = PREDEFINED_RECORDS[0]["server_seed"]
        assert mechanism.commit(seed) == mechanism.commit(seed)

    def test_different_seeds_produce_different_commitments(self, mechanism):
        commitment_a = mechanism.commit(PREDEFINED_RECORDS[0]["server_seed"])
        commitment_b = mechanism.commit(PREDEFINED_RECORDS[1]["server_seed"])
        assert commitment_a != commitment_b

    def test_verify_commitment_passes_with_correct_seed(self, mechanism):
        seed = PREDEFINED_RECORDS[0]["server_seed"]
        commitment = mechanism.commit(seed)
        assert mechanism.verify_commitment(seed, commitment) is True

    def test_verify_commitment_fails_with_wrong_seed(self, mechanism):
        seed = PREDEFINED_RECORDS[0]["server_seed"]
        commitment = mechanism.commit(seed)
        assert mechanism.verify_commitment("wrong-seed", commitment) is False

    def test_verify_commitment_fails_with_tampered_commitment(self, mechanism):
        seed = PREDEFINED_RECORDS[0]["server_seed"]
        tampered_commitment = "0" * 64
        assert mechanism.verify_commitment(seed, tampered_commitment) is False

    def test_commitment_changes_after_seed_rotation(self, mechanism):
        old_commitment = mechanism.commit(PREDEFINED_RECORDS[0]["server_seed"])
        new_seed = mechanism.get_entropy().hex()
        new_commitment = mechanism.commit(new_seed)
        assert old_commitment != new_commitment


# ---------------------------------------------------------------------------
# Entropy tests
# ---------------------------------------------------------------------------


class TestEntropy:

    def test_get_entropy_returns_bytes(self, mechanism):
        assert isinstance(mechanism.get_entropy(), bytes)

    def test_get_entropy_returns_32_bytes(self, mechanism):
        assert len(mechanism.get_entropy()) == 32

    def test_get_entropy_is_not_deterministic(self, mechanism):
        # Two consecutive calls must not return identical values.
        # The probability of a false failure is 1/2^256.
        assert mechanism.get_entropy() != mechanism.get_entropy()

    def test_entropy_suitable_as_server_seed(self, mechanism):
        seed = mechanism.get_entropy().hex()
        commitment = mechanism.commit(seed)
        assert len(commitment) == 64  # SHA-256 hex digest is always 64 chars
