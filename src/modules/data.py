from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class TestResult:
    """Represents the result of a single test."""
    test_name: str
    p_value: float
    passed: bool
    parameters_used: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # scipy comparisons return np.bool_ — normalise to plain Python bool.
        self.passed = bool(self.passed)


@dataclass
class BinaryResult:
    """Represents the result of a binary test."""
    test_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
