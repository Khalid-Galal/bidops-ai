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

    # LLM settings (Phase 3)
    gemini_api_key: str = ""
    # Optional comma-separated list of keys; enables rotation/failover across
    # per-key free-tier rate limits. Takes precedence over gemini_api_key.
    gemini_api_keys: str = ""
    gemini_model: str = "gemini-2.5-pro"

    # NLI citation verification (Phase 3)
    nli_model: str = "cross-encoder/nli-deberta-v3-xsmall"

    # SMTP transport for outbound email (Phase 9). Empty host/user => "not
    # configured": drafts still work, but POST /send returns 503. Set these in
    # .env with the BIDOPS_ prefix (e.g. BIDOPS_SMTP_HOST=...) to enable sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Sender identity (Phase 9). from_address resolution order at send time:
    # rules.email.from_address -> settings.email_from -> settings.smtp_user.
    email_from: str = ""
    email_from_name: str = "BidOps AI"
    company_name: str = "BidOps"

    # Confidence thresholds (Phase 3)
    confidence_high_threshold: float = 0.8
    confidence_low_threshold: float = 0.5
    review_threshold: float = 0.5

    def gemini_key_list(self) -> list[str]:
        """Return configured Gemini API keys (rotation list preferred).

        Uses ``gemini_api_keys`` (comma-separated) if set, otherwise falls back
        to the single ``gemini_api_key``. Empty entries are dropped.
        """
        raw = self.gemini_api_keys or self.gemini_api_key
        return [k.strip() for k in raw.split(",") if k.strip()]

    model_config = {
        "env_prefix": "BIDOPS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
