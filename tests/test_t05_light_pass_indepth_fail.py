"""
T-5: Light Pass, In-Depth Fail Progression

A fully correct HMAC mechanism is evaluated with adaptive_threshold=2. By the
birthday bound, any Stake outcome value is virtually guaranteed to appear >= 2
times in a 512-sample window across 600 rolls, so the adaptive proportion test
fires. The engine must not progress to FULL_DEPTH after this IN_DEPTH failure.
"""
from src.enigines.config import EvaluationConfig
from src.enigines.evaluation import EvaluationEngine
from src.provably_fair_mechanisms.hmac_mechanism import StakesHMACMechanism, stake_dice_outcome


def test_light_passes_indepth_fails_gating_prevents_full_depth(tmp_path):
    config = EvaluationConfig(
        n_faces=6,
        adaptive_threshold=2,
        server_seed_min_entropy_threshold_bits=0.0,
        n_latency_requests=50,
        n_startup_requests=50,
        n_load_requests=10,
    )
    mechanism = StakesHMACMechanism(str(tmp_path / "rolls.csv"))
    rolls = mechanism.generate_rolls(600, save_rolls=False)

    engine = EvaluationEngine(mechanism, str(tmp_path / "result.json"), config)
    result = engine.run_evaluation(rolls, "IN_DEPTH", mapping_fn=stake_dice_outcome)

    assert result.randomness.light.sanity_check.passed
    assert result.security.light.nonce_presence.passed

    assert result.randomness.in_depth is not None
    assert not result.randomness.in_depth.entropy_monitoring["adaptive_proportion"].passed

    assert result.halted_at == "IN_DEPTH"
    assert result.randomness.full_depth is None
    assert result.performance.in_depth is None
