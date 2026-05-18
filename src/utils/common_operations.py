from src.config.configs import MAX_VALUE, REJECTION_THRESHOLD


def rejection_sampling(
    raw_output: bytes,
    rejection_threshold: int = REJECTION_THRESHOLD,
    max_value: int = MAX_VALUE,
) -> int:
    """
    Maps a 32-byte HMAC digest (raw_output) to an outcome in the range
    [0, MAX_VALUE] using rejection sampling.
    """
    for i in range(8):
        chunk = int.from_bytes(raw_output[i * 4 : i * 4 + 4], "big")

        if chunk < rejection_threshold:
            return (chunk % max_value) + 1

    raise ValueError(
        "Rejection sampling exhausted all chunks in the digest without "
        "finding an accepted value. This is an incredibly rare event "
        "and likely indicates a bug in the digest or threshold calculation."
    )


def chi_square_test(observed: list[int], expected: list[float]) -> tuple[float, float]:
    """
    Perform a chi-square test comparing observed and expected frequencies.
    Returns the chi-square statistic and p-value.
    """
    from scipy.stats import chisquare

    stat, p_value = chisquare(f_obs=observed, f_exp=expected)
    return float(stat), float(p_value)
