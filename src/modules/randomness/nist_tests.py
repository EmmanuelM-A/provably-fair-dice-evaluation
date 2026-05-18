"""
NIST SP 800-22 statistical test battery for randomness evaluation.

Tests 1-7 run under LightEvaluationNistTests (minimum 20,000 bits).
Tests 8-10 run under InDepthEvaluationNistTests (minimum 1,000,000 bits).

Reference: Rukhin et al., "A Statistical Test Suite for Random and
Pseudorandom Number Generators for Cryptographic Applications",
NIST SP 800-22 Rev. 1a.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import math
import numpy as np
from scipy import special, stats

from src.modules.data import TestResult

SIGNIFICANCE_LEVEL = 0.01


class NistTests(ABC):
    @abstractmethod
    def run_all_tests(
        self, bit_sequence: bytes, sequence_length: int
    ) -> dict[str, TestResult]:
        raise NotImplementedError()


def _to_bit_array(bit_sequence: bytes, sequence_length: int) -> np.ndarray:
    """Convert a byte sequence to a numpy array of 0s and 1s, truncated to sequence_length."""
    bits = np.unpackbits(np.frombuffer(bit_sequence, dtype=np.uint8))
    return bits[:sequence_length].astype(np.int8)


# ---------------------------------------------------------------------------
# Test 1: Frequency (Monobit) Test
# ---------------------------------------------------------------------------


def _frequency_monobit_test(bits: np.ndarray) -> TestResult:
    """
    NIST SP 800-22 Section 2.1.

    Determines whether the number of ones and zeros in the sequence are
    approximately equal, as expected for a truly random sequence.
    """
    n = len(bits)
    s_n = np.sum(2 * bits - 1)
    s_obs = abs(s_n) / math.sqrt(n)
    p_value = math.erfc(s_obs / math.sqrt(2))

    return TestResult(
        test_name="Frequency (Monobit) Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={"n": n, "s_obs": s_obs},
    )


# ---------------------------------------------------------------------------
# Test 2: Frequency within a Block
# ---------------------------------------------------------------------------


def _frequency_block_test(bits: np.ndarray, block_size: int = 128) -> TestResult:
    """
    NIST SP 800-22 Section 2.2.

    Determines whether the frequency of ones in each M-bit block is
    approximately M/2.
    """
    n = len(bits)
    m = block_size
    num_blocks = n // m
    blocks = bits[: num_blocks * m].reshape(num_blocks, m)
    proportions = blocks.mean(axis=1)
    chi_sq = 4.0 * m * np.sum((proportions - 0.5) ** 2)
    p_value = special.gammaincc(num_blocks / 2.0, chi_sq / 2.0)

    return TestResult(
        test_name="Frequency within a Block",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={"n": n, "M": m, "N": num_blocks, "chi_sq": chi_sq},
    )


# ---------------------------------------------------------------------------
# Test 3: Runs Test
# ---------------------------------------------------------------------------


def _runs_test(bits: np.ndarray) -> TestResult:
    """
    NIST SP 800-22 Section 2.3.

    Determines whether the number of runs (uninterrupted sequences of identical
    bits) is consistent with what is expected for a random sequence.
    """
    n = len(bits)
    pi = bits.mean()

    # Pre-test: if pi is too far from 0.5, the p-value is 0.
    if abs(pi - 0.5) >= 2.0 / math.sqrt(n):
        return TestResult(
            test_name="Runs Test",
            p_value=0.0,
            passed=False,
            parameters_used={"n": n, "pi": pi, "pre_test_failed": True},
        )

    v_obs = 1 + np.sum(bits[:-1] != bits[1:])
    numerator = abs(v_obs - 2.0 * n * pi * (1.0 - pi))
    denominator = 2.0 * math.sqrt(2.0 * n) * pi * (1.0 - pi)
    p_value = math.erfc(numerator / denominator)

    return TestResult(
        test_name="Runs Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={"n": n, "pi": pi, "v_obs": int(v_obs)},
    )


# ---------------------------------------------------------------------------
# Test 4: Longest Run of Ones in a Block
# ---------------------------------------------------------------------------


def _longest_run_ones_test(bits: np.ndarray) -> TestResult:
    """
    NIST SP 800-22 Section 2.4.

    Determines whether the longest run of ones within M-bit blocks is
    consistent with the expected distribution for a random sequence.
    Uses the M=8 block variant (n >= 128 bits).
    """
    n = len(bits)
    m = 8
    num_blocks = n // m

    # Theoretical probabilities for M=8 (from NIST SP 800-22, Table 1)
    # Categories: v <= 1, v=2, v=3, v=4, v=5, v >= 6
    pi = [0.2148, 0.3672, 0.2305, 0.1284, 0.0527, 0.0064]
    k = 5  # number of degrees of freedom = len(pi) - 1

    # Count longest run of ones in each block
    blocks = bits[: num_blocks * m].reshape(num_blocks, m)
    longest_runs = []
    for block in blocks:
        max_run = 0
        current_run = 0
        for bit in block:
            if bit == 1:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0
        longest_runs.append(max_run)

    # Map run lengths to categories
    counts = np.zeros(k + 1, dtype=float)
    for run in longest_runs:
        if run <= 1:
            counts[0] += 1
        elif run <= 5:
            counts[run - 1] += 1
        else:
            counts[5] += 1

    expected = np.array(pi) * num_blocks
    chi_sq = float(np.sum((counts - expected) ** 2 / expected))
    p_value = special.gammaincc(k / 2.0, chi_sq / 2.0)

    return TestResult(
        test_name="Longest Run of Ones in a Block",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={"n": n, "M": m, "N": num_blocks, "chi_sq": chi_sq},
    )


# ---------------------------------------------------------------------------
# Test 5: Binary Matrix Rank Test
# ---------------------------------------------------------------------------


def _binary_matrix_rank_test(bits: np.ndarray, matrix_size: int = 32) -> TestResult:
    """
    NIST SP 800-22 Section 2.5.

    Checks for linear dependence among fixed-length substrings of the sequence.
    Uses 32x32 matrices by default (requires at least 38,912 bits).
    """
    n = len(bits)
    m = q = matrix_size
    num_matrices = n // (m * q)

    def _gf2_rank(matrix: np.ndarray) -> int:
        """Compute the rank of a binary matrix over GF(2)."""
        mat = matrix.copy().astype(np.uint8)
        rank = 0
        for col in range(mat.shape[1]):
            pivot_row = None
            for row in range(rank, mat.shape[0]):
                if mat[row, col] == 1:
                    pivot_row = row
                    break
            if pivot_row is None:
                continue
            mat[[rank, pivot_row]] = mat[[pivot_row, rank]]
            for row in range(mat.shape[0]):
                if row != rank and mat[row, col] == 1:
                    mat[row] = (mat[row] + mat[rank]) % 2
            rank += 1
        return rank

    ranks = []
    for i in range(num_matrices):
        block = bits[i * m * q : (i + 1) * m * q].reshape(m, q)
        ranks.append(_gf2_rank(block))

    ranks = np.array(ranks)
    f_m = np.sum(ranks == m)
    f_m1 = np.sum(ranks == m - 1)
    f_rest = num_matrices - f_m - f_m1

    # Theoretical probabilities for large M=Q=32 (from NIST SP 800-22)
    p_full = 0.2888
    p_m1 = 0.5776
    p_rest = 0.1336

    expected = np.array([p_full, p_m1, p_rest]) * num_matrices
    observed = np.array([f_m, f_m1, f_rest], dtype=float)

    chi_sq = float(np.sum((observed - expected) ** 2 / expected))
    p_value = math.exp(-chi_sq / 2.0)

    return TestResult(
        test_name="Binary Matrix Rank Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n": n,
            "M": m,
            "Q": q,
            "num_matrices": num_matrices,
            "chi_sq": chi_sq,
        },
    )


# ---------------------------------------------------------------------------
# Test 6: Discrete Fourier Transform (Spectral) Test
# ---------------------------------------------------------------------------


def _dft_spectral_test(bits: np.ndarray) -> TestResult:
    """
    NIST SP 800-22 Section 2.6.

    Detects periodic features in the sequence that would indicate a deviation
    from the assumption of randomness.
    """
    n = len(bits)
    x = 2 * bits.astype(float) - 1
    dft = np.fft.fft(x)
    magnitudes = np.abs(dft[: n // 2])
    threshold = math.sqrt(2.995732274 * n)  # 95th percentile threshold
    n_below = np.sum(magnitudes < threshold)
    expected_below = 0.95 * (n // 2)
    d = (n_below - expected_below) / math.sqrt(n * 0.95 * 0.05 / 4.0)
    p_value = math.erfc(abs(d) / math.sqrt(2))

    return TestResult(
        test_name="Discrete Fourier Transform (Spectral) Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n": n,
            "threshold": threshold,
            "n_below_threshold": int(n_below),
            "expected_below_threshold": expected_below,
        },
    )


# ---------------------------------------------------------------------------
# Test 7: Cumulative Sums (Cusum) Test
# ---------------------------------------------------------------------------


def _cumulative_sums_test(bits: np.ndarray) -> TestResult:
    """
    NIST SP 800-22 Section 2.13.

    Determines whether the cumulative sum of the partial sequences occurring
    in the tested sequence is too large or too small relative to the expected
    behaviour of a random sequence.

    Runs both the forward and backward modes and returns the minimum p-value.
    """
    n = len(bits)
    x = 2 * bits.astype(float) - 1

    def _cusum_p_value(sequence: np.ndarray) -> float:
        cumsum = np.cumsum(sequence)
        z = int(np.max(np.abs(cumsum)))

        def _phi(t: float) -> float:
            return float(stats.norm.cdf(t))

        p = 0.0
        lower = int(math.floor((-n / z + 1) / 4))
        upper = int(math.floor((n / z - 1) / 4))
        for k in range(lower, upper + 1):
            p += _phi((4 * k + 1) * z / math.sqrt(n)) - _phi(
                (4 * k - 1) * z / math.sqrt(n)
            )

        lower2 = int(math.floor((-n / z - 3) / 4))
        upper2 = int(math.floor((n / z - 1) / 4))
        for k in range(lower2, upper2 + 1):
            p -= _phi((4 * k + 3) * z / math.sqrt(n)) - _phi(
                (4 * k + 1) * z / math.sqrt(n)
            )

        return 1.0 - p

    p_forward = _cusum_p_value(x)
    p_backward = _cusum_p_value(x[::-1])
    p_value = min(p_forward, p_backward)

    return TestResult(
        test_name="Cumulative Sums Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n": n,
            "p_value_forward": p_forward,
            "p_value_backward": p_backward,
        },
    )


# ---------------------------------------------------------------------------
# Test 8: Approximate Entropy Test
# ---------------------------------------------------------------------------


def _approximate_entropy_test(bits: np.ndarray, m: int = 10) -> TestResult:
    """
    NIST SP 800-22 Section 2.12.

    Compares the frequency of overlapping m-bit patterns with the frequency
    of overlapping (m+1)-bit patterns to assess regularity of the sequence.
    """
    n = len(bits)

    def _phi(block_len: int) -> float:
        counts: Dict[tuple, int] = {}
        for i in range(n):
            pattern = tuple(bits[np.arange(i, i + block_len) % n])
            counts[pattern] = counts.get(pattern, 0) + 1
        total = sum(counts.values())
        return sum((c / total) * math.log(c / total) for c in counts.values())

    phi_m = _phi(m)
    phi_m1 = _phi(m + 1)
    ap_en = phi_m - phi_m1
    chi_sq = 2.0 * n * (math.log(2) - ap_en)
    p_value = special.gammaincc(2 ** (m - 1), chi_sq / 2.0)

    return TestResult(
        test_name="Approximate Entropy Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={"n": n, "m": m, "ApEn": ap_en, "chi_sq": chi_sq},
    )


# ---------------------------------------------------------------------------
# Test 9: Serial Test
# ---------------------------------------------------------------------------


def _serial_test(bits: np.ndarray, m: int = 16) -> TestResult:
    """
    NIST SP 800-22 Section 2.11.

    Determines whether the frequency of all overlapping m-bit patterns across
    the sequence is approximately equal, as would be expected for a random sequence.

    Returns the minimum of the two derived p-values (delta1 and delta2).
    """
    n = len(bits)

    def _psi_sq(block_len: int) -> float:
        if block_len == 0:
            return 0.0
        counts: Dict[tuple, int] = {}
        for i in range(n):
            pattern = tuple(bits[np.arange(i, i + block_len) % n])
            counts[pattern] = counts.get(pattern, 0) + 1
        return (2**block_len / n) * sum(c**2 for c in counts.values()) - n

    psi_m = _psi_sq(m)
    psi_m1 = _psi_sq(m - 1)
    psi_m2 = _psi_sq(m - 2)

    delta1 = psi_m - psi_m1
    delta2 = psi_m - 2.0 * psi_m1 + psi_m2

    p1 = special.gammaincc(2 ** (m - 2), delta1 / 2.0)
    p2 = special.gammaincc(2 ** (m - 3), delta2 / 2.0)
    p_value = min(p1, p2)

    return TestResult(
        test_name="Serial Test",
        p_value=p_value,
        passed=p_value >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n": n,
            "m": m,
            "delta1": delta1,
            "delta2": delta2,
            "p_value_1": p1,
            "p_value_2": p2,
        },
    )


# ---------------------------------------------------------------------------
# Test 10: Random Excursions Test
# ---------------------------------------------------------------------------


def _random_excursions_test(bits: np.ndarray) -> TestResult:
    """
    NIST SP 800-22 Section 2.14.

    Determines whether the number of visits to each state in a random walk
    through the sequence matches the expected distribution.

    Returns the minimum p-value across all eight tested states
    (x = -4, -3, -2, -1, +1, +2, +3, +4).

    Requires at least 500 complete cycles (returns to 0) for validity.
    """
    n = len(bits)
    x = 2 * bits.astype(int) - 1
    cumsum = np.concatenate([[0], np.cumsum(x), [0]])

    # Find cycle boundaries (positions where cumsum returns to 0)
    zero_crossings = np.where(cumsum == 0)[0]
    num_cycles = len(zero_crossings) - 1

    if num_cycles < 500:
        return TestResult(
            test_name="Random Excursions Test",
            p_value=0.0,
            passed=False,
            parameters_used={
                "n": n,
                "num_cycles": num_cycles,
                "error": "Insufficient cycles (< 500). Sequence too short or not sufficiently random.",
            },
        )

    # Theoretical probabilities for visit counts k=0..5+ for each state x
    # pi[x][k]: probability of k visits to state x in one cycle
    def _pi(x: int, k: int) -> float:
        abs_x = abs(x)
        if k == 0:
            return 1.0 - 1.0 / (2.0 * abs_x)
        if k >= 5:
            return (1.0 / (2.0 * abs_x)) * (1.0 - 1.0 / (2.0 * abs_x)) ** 4
        return (1.0 / (4.0 * abs_x**2)) * (1.0 - 1.0 / (2.0 * abs_x)) ** (k - 1)

    states = [-4, -3, -2, -1, 1, 2, 3, 4]
    p_values = {}

    for state in states:
        # Count visits to `state` in each cycle
        visit_counts = []
        for i in range(num_cycles):
            start = zero_crossings[i]
            end = zero_crossings[i + 1]
            cycle = cumsum[start : end + 1]
            visit_counts.append(int(np.sum(cycle == state)))

        # Build frequency table for visit counts 0..5+
        freq = np.zeros(6)
        for v in visit_counts:
            freq[min(v, 5)] += 1

        expected = np.array([_pi(state, k) * num_cycles for k in range(6)])
        chi_sq = float(np.sum((freq - expected) ** 2 / expected))
        p = special.gammaincc(5.0 / 2.0, chi_sq / 2.0)
        p_values[state] = p

    min_p = min(p_values.values())

    return TestResult(
        test_name="Random Excursions Test",
        p_value=min_p,
        passed=min_p >= SIGNIFICANCE_LEVEL,
        parameters_used={
            "n": n,
            "num_cycles": num_cycles,
            "p_values_per_state": p_values,
        },
    )


# ---------------------------------------------------------------------------
# Concrete subclass implementations
# ---------------------------------------------------------------------------


class LightEvaluationNistTests(NistTests):
    """
    Runs tests 1-7 against a bit sequence of at least 20,000 bits.
    """

    MIN_BITS = 20_000

    def run_all_tests(
        self, bit_sequence: bytes, sequence_length: int = 20_000
    ) -> dict[str, TestResult]:
        if sequence_length < self.MIN_BITS:
            raise ValueError(
                f"LightEvaluationNistTests requires at least {self.MIN_BITS} bits. "
                f"Got {sequence_length}."
            )

        bits = _to_bit_array(bit_sequence, sequence_length)

        results = {}

        results["frequency_monobit"] = _frequency_monobit_test(bits)
        results["frequency_block"] = _frequency_block_test(bits, block_size=128)
        results["runs"] = _runs_test(bits)
        results["longest_run_ones"] = _longest_run_ones_test(bits)
        results["binary_matrix_rank"] = _binary_matrix_rank_test(bits, matrix_size=32)
        results["dft_spectral"] = _dft_spectral_test(bits)
        results["cumulative_sums"] = _cumulative_sums_test(bits)

        return results


class InDepthEvaluationNistTests(NistTests):
    """
    Runs tests 8-10 against a bit sequence of at least 1,000,000 bits.
    """

    MIN_BITS = 1_000_000

    def run_all_tests(
        self, bit_sequence: bytes, sequence_length: int = 1_000_000
    ) -> dict[str, TestResult]:
        if sequence_length < self.MIN_BITS:
            raise ValueError(
                f"InDepthEvaluationNistTests requires at least {self.MIN_BITS} bits. "
                f"Got {sequence_length}."
            )

        bits = _to_bit_array(bit_sequence, sequence_length)

        results = {}

        results["approximate_entropy"] = _approximate_entropy_test(bits, m=10)
        results["serial"] = _serial_test(bits, m=16)
        results["random_excursions"] = _random_excursions_test(bits)

        return results
