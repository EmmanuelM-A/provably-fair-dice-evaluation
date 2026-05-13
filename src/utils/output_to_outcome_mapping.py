def rejection_sampling(
    raw_output: bytes,
    rejection_threshold: int,
    max_value: int
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
