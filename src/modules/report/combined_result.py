from dataclasses import dataclass
from typing import Optional

from src.enigines.evaluation import EvaluationResult


@dataclass
class CombinedEvaluationReport:
    tier: str
    programmable: EvaluationResult
    non_programmable: Optional[dict] = None
