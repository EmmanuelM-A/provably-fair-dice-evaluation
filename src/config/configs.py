"""
Configuration settings for the DocuChatAPI application.
Each configuration class handles a specific domain of settings.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

from src.logger.logging_utils import LogLevel

# ------------------------------------------------------------------
# Environment Setup
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

_DEFAULT_MODEL_CONFIG = SettingsConfigDict(
    env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
)


# ------------------------------------------------------------------
# App Settings
# ------------------------------------------------------------------
class AppSettings(BaseSettings):
    """Application configuration settings."""

    LOG_LEVEL: str = Field(default=LogLevel.DEBUG)
    LOG_DIRECTORY: str = Field(default=f"{PROJECT_ROOT}/logs")
    LOG_FORMAT: str = Field(
        default="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    )
    DATE_FORMAT: str = Field(default="%Y-%m-%d %H:%M:%S")

    model_config = _DEFAULT_MODEL_CONFIG


# ------------------------------------------------------------------
# Main Settings Container
# ------------------------------------------------------------------
class Settings(BaseSettings):
    """Main settings container aggregating all configuration domains."""

    app: AppSettings = AppSettings()

    model_config = _DEFAULT_MODEL_CONFIG


# Global settings instance
settings = Settings()