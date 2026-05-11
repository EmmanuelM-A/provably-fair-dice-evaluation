"""
Contains shared types and data structures used throughout the codebase.
"""
from dataclasses import dataclass


@dataclass
class RollRecord:
    server_seed: str
    client_seed: str
    nonce: str
    raw_output: bytes
    outcome: int
    timestamp: float
    mechanism_id: str


@dataclass
class VerificationResult:
    record: RollRecord
    disclosed_server_seed: str
    recomputed_outcome: int
    match: bool
