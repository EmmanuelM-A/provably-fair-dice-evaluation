import argparse

from src.config.configs import MAX_VALUE
from src.enigines.evaluation import EvaluationConfig, EvaluationEngine
from src.provably_fair_mechanisms.hmac_mechanism import HMACMechanism
from src.utils.data_loader import load_roll_records_from

HMAC_OUTPUT = "data/rolls/hmac_rolls.csv"
HMAC_RESULTS = "data/results/hmac_eval_results.json"


HMAC_CONFIG = EvaluationConfig(
    n_faces=MAX_VALUE,
    distribution_min_rolls=500,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of rolls to generate.",
    )
    args = parser.parse_args()

    mechanism = HMACMechanism(output_file=HMAC_OUTPUT)
    # rolls = mechanism.generate_rolls(args.count)
    rolls = load_roll_records_from(HMAC_OUTPUT)

    mechanism_eval = EvaluationEngine(mechanism=mechanism, config=HMAC_CONFIG)
    mechanism_eval.evaluate_randomness(rolls)
    mechanism_eval.evaluate_security(rolls)
    mechanism_eval.evaluate_performance()
    mechanism_eval.save_results(HMAC_RESULTS)


if __name__ == "__main__":
    """
    Usage: python -m src.main --count <number_of_rolls>
    """
    main()
