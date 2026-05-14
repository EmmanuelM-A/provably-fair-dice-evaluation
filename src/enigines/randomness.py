"""
Defines the RandomnessEngine interface, which is used to generate random numbers
based on the provided inputs, aimed at simulating the roll requests from your
implemented provably fair dice mechanism.
"""

from abc import ABC, abstractmethod
from typing import List

from src.utils.types import RollRecord


class RandomnessEngine(ABC):
    """
    Defines all the mandatory operations required to simulate random number
    generation.
    """

    @abstractmethod
    def generate_rolls(self, quantity: int, output_file: str) -> List[RollRecord]:
        """
        Generates a dataset of random rolls based your defined/simulated PFD
        mechanism.
        """
        raise NotImplementedError()
