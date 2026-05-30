from dataclasses import dataclass


@dataclass
class EvaluationConfig:
    # Number of distinct outcome values the mechanism can produce (die faces).
    # Must match the actual output range of the mechanism under evaluation.
    # With n_faces=F, the chi-square test requires at least 5*F rolls.
    n_faces: int = 6
    
    significance_level: float = 0.01

    # Minimum rolls required before any distribution test runs.
    distribution_min_rolls: int = 500

    # NIST tier thresholds (bits). Tiers are skipped when insufficient bits
    # are available from the concatenated raw_output of the roll records.
    nist_light_min_bits: int = 20_000
    nist_in_depth_min_bits: int = 1_000_000

    # Server seed entropy source validation (NIST SP 800-90B §3).
    # Minimum acceptable min-entropy in bits: H_min = -log2(p_max) must meet
    # or exceed this value. 8.0 bits is the practical floor for health testing
    # — with the minimum 500-roll sample, this requires all seeds to be unique.
    server_seed_min_entropy_threshold_bits: float = 8.0

    # Repetition Count Test (NIST SP 800-90B §4.4.1).
    # threshold_c: consecutive identical values that trigger an alarm.
    repetition_threshold_c: int = 20

    # Adaptive Proportion Test (NIST SP 800-90B §4.4.2).
    # window_w: sliding window width; adaptive_threshold: max count per window.
    adaptive_window_w: int = 512
    adaptive_threshold: int = 120
    
    n_latency_requests: int = 1_000
    n_startup_requests: int = 10_000
    n_load_requests: int = 200
