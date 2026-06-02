"""
T-4: Fully Compliant Mechanism Progression

A correctly implemented HMAC-SHA256 mechanism with CSPRNG seed, proper nonces,
and rejection-sampling-equivalent mapping passes all Light checks, progresses
to In-Depth, passes those too, and returns a complete result with no gate halt.
"""
from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.provably_fair_mechanisms.hmac_mechanism import StakesHMACMechanism, stake_dice_outcome


def test_fully_compliant_mechanism_passes_light_and_in_depth(tmp_path):
    config = EvaluationConfig(
        n_faces=6,
        server_seed_min_entropy_threshold_bits=0.0,
        n_latency_requests=50,
        n_startup_requests=50,
        n_load_requests=10,
    )
    mechanism = StakesHMACMechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    result = engine.run_evaluation(rolls, "IN_DEPTH", mapping_fn=stake_dice_outcome)

    assert result.halted_at is None

    assert result.randomness.light.sanity_check.passed
    assert result.randomness.light.cramer_von_mises.passed
    assert result.randomness.light.runs_independence.passed

    assert result.security.light.nonce_presence.passed
    assert result.security.light.nonce_uniqueness.passed

    assert result.randomness.in_depth is not None
    assert result.randomness.in_depth.entropy_monitoring["adaptive_proportion"].passed
    assert result.randomness.in_depth.entropy_monitoring["repetition_count"].passed
