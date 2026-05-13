"""
Configuration settings for the DocuChatAPI application.
Each configuration class handles a specific domain of settings.
"""

from pathlib import Path

from src.logger.logging_utils import LogLevel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


LOG_LEVEL: str = LogLevel.DEBUG
LOG_DIRECTORY: str = f"{PROJECT_ROOT}/logs"
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

MAX_UINT32: int = 2**32
MAX_VALUE: int = 10_000
REJECTION_THRESHOLD: int = (MAX_UINT32 // MAX_VALUE) * MAX_VALUE
