from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class TestResult:
    test_name: str
    p_value: float
    passed: bool
    parameters_used: Dict[str, Any] = field(default_factory=dict)
