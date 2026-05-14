"""
Configuration settings for the Provably Fair Dice Evaluation Framework.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


LOG_DIRECTORY: str = f"{PROJECT_ROOT}/logs"
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

QUANTITY_OF_ROLLS: int = 10
MAX_UINT32: int = 2**32
MAX_VALUE: int = 10_000
REJECTION_THRESHOLD: int = (MAX_UINT32 // MAX_VALUE) * MAX_VALUE
