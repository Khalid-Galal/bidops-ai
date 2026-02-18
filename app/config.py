"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    database_path: str = "data/bidops.db"
    upload_dir: str = "data/uploads"
    debug: bool = False
    app_title: str = "BidOps AI"

    model_config = {
        "env_prefix": "BIDOPS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
