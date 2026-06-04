"""
Contains shared types and data structures used throughout the codebase.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RollRecord:
    """Represents a single random number generation record with all relevant fields."""
    server_seed: str
    client_seed: str
    nonce: int
    raw_output: bytes
    outcome: float
    timestamp: datetime
    mechanism_id: str


@dataclass
class VerificationResult:
    """Represents the result of verifying a single roll record."""
    record: RollRecord
    disclosed_server_seed: str
    recomputed_outcome: float
    match: bool
