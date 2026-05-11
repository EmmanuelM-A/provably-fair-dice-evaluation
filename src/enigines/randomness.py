"""
Defines the RandomnessEngine interface, which is used to generate random numbers
based on the provided inputs, aimed at simulating the roll requests from your
implemented provably fair dice mechanism.
"""

from abc import ABC, abstractmethod

from src.utils.types import RollRecord


class RandomnessEngine(ABC):
    """
    Defines all the mandatory operations required to simulate random number
    generation.
    """

    @abstractmethod
    def get_entropy(self) -> bytes:
        """
        Returns the entropy of the random number generator.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_noise(self) -> bytes:
        """
        Returns the noise of the random number generator.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_drbg_instance(self) -> any:  # NOTE: Come back to this!
        """
        Returns the random number generator used to generate random numbers.
        """
        raise NotImplementedError()

    @abstractmethod
    def generate_number(
        self, server_seed: str, client_seed: str, nonce: str = ""
    ) -> RollRecord:
        """
        Generates a random roll number using the provided server seed, client
        seed and nonce.
        """
        raise NotImplementedError()
