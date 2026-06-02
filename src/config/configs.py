"""
Configuration settings for the Provably Fair Dice Evaluation Framework.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SEED: int = 42

LOG_DIRECTORY: str = f"{PROJECT_ROOT}/logs"
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

REPORTS_DIRECTORY: str = f"{PROJECT_ROOT}/results/reports"
PER_DIRECTORY: str = f"{PROJECT_ROOT}/results/programmable"
NPER_DIRECTORY: str = f"{PROJECT_ROOT}/results/non_programmable"
ROLLS_DIRECTORY: str = f"{PROJECT_ROOT}/results/rolls"

MAX_UINT32: int = 2**32
MAX_VALUE: int = 100
REJECTION_THRESHOLD: int = (MAX_UINT32 // MAX_VALUE) * MAX_VALUE

# Lower-bound block for coordinator event log scans. Set this to the block at
# which your VRF coordinator contract was deployed to avoid scanning from genesis.
VRF_COORDINATOR_DEPLOY_BLOCK: int = int(os.environ.get("VRF_COORDINATOR_DEPLOY_BLOCK", 0))
