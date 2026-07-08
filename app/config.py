"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    database_path: str = "data/bidops.db"
    upload_dir: str = "data/uploads"
    debug: bool = False
    app_title: str = "BidOps AI"
    app_version: str = "0.1.0"

    # NFR / hardening (Phase 15). Rate limiting is OFF by default (single-user
    # local app); when enabled it is a per-client-IP token bucket.
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 30
    # Load the embedding/NLI models in a background thread at startup so the
    # first ingest/search is not slow. Off by default so the test suite and
    # pure-pricing workflows never pay the cost.
    warmup_models_on_startup: bool = False

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
    # Generation temperature for all Gemini calls. Low by default because
    # extraction/verification tasks need verbatim, deterministic-ish output,
    # not creative variance.
    llm_temperature: float = 0.1

    # NLI citation verification (Phase 3)
    nli_model: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

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

    # Free-tier persistence: snapshot data/ to a private HF Dataset repo and
    # restore it on a fresh boot. Enabled when BOTH backup_dataset_repo and a
    # write token (BIDOPS_HF_TOKEN, or the standard HF_TOKEN env var) are set.
    backup_dataset_repo: str = ""  # e.g. "Khaled-Galal/bidops-data"
    hf_token: str = ""
    backup_interval_seconds: int = 60

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
