"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    database_path: str = "data/bidops.db"
    upload_dir: str = "data/uploads"
    debug: bool = False
    app_title: str = "BidOps AI"

    # ChromaDB vector storage (Phase 2)
    chroma_persist_dir: str = "data/chroma"
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"

    # Chunking parameters (Phase 2)
    chunk_max_chars: int = 400
    chunk_overlap_chars: int = 50

    model_config = {
        "env_prefix": "BIDOPS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
