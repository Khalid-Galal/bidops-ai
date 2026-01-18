"""Application configuration management."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "BidOps AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://bidops:bidops@localhost:5432/bidops",
        description="PostgreSQL connection string",
    )
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Vector Database (Qdrant)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "bidops_documents"

    # Authentication
    SECRET_KEY: str = Field(
        default="change-this-secret-key-in-production",
        description="Secret key for JWT signing",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Google Gemini
    GOOGLE_API_KEY: str = ""
    GEMINI_FLASH_MODEL: str = "gemini-2.5-flash-latest"
    GEMINI_PRO_MODEL: str = "gemini-2.5-pro"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"

    # Storage
    STORAGE_PATH: Path = Path("./storage")
    PROJECTS_PATH: Path = Path("./storage/projects")
    TEMP_PATH: Path = Path("./storage/temp")
    DATABASE_PATH: Path = Path("./storage/database")

    # File Processing
    MAX_UPLOAD_SIZE_MB: int = 500
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # OCR
    TESSERACT_CMD: str = "tesseract"
    TESSERACT_LANG: str = "eng+ara"

    # CAD Processing
    ODA_CONVERTER_PATH: str = ""

    # Email
    EMAIL_PROVIDER: Literal["graph", "smtp"] = "smtp"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # Microsoft Graph
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    AZURE_TENANT_ID: str = ""

    # Confidence Thresholds
    CONFIDENCE_THRESHOLD: float = 0.7
    REVIEW_THRESHOLD: float = 0.5

    @field_validator("STORAGE_PATH", "PROJECTS_PATH", "TEMP_PATH", "DATABASE_PATH", mode="before")
    @classmethod
    def ensure_path(cls, v):
        """Ensure path is a Path object."""
        return Path(v) if isinstance(v, str) else v

    def setup_directories(self):
        """Create required directories if they don't exist."""
        for path in [self.STORAGE_PATH, self.PROJECTS_PATH, self.TEMP_PATH, self.DATABASE_PATH]:
            path.mkdir(parents=True, exist_ok=True)


class RulesConfig:
    """Load and manage rules configuration from YAML."""

    def __init__(self, config_path: str = "config/rules.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return self._default_config()

    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            "scoring": {
                "weights": {
                    "technical_compliance": 0.30,
                    "price": 0.35,
                    "delivery_time": 0.15,
                    "payment_terms": 0.10,
                    "supplier_rating": 0.10,
                }
            },
            "packaging": {
                "min_items_per_package": 5,
                "max_items_per_package": 100,
                "grouping_criteria": ["trade_category", "spec_section"],
            },
            "commercial": {
                "currency": "AED",
                "vat_rate": 0.05,
                "default_validity_days": 90,
                "default_payment_terms": "Net 30",
            },
            "llm": {
                "confidence_threshold": 0.7,
                "require_review_below": 0.5,
            },
        }

    @property
    def scoring_weights(self) -> dict:
        return self._config.get("scoring", {}).get("weights", {})

    @property
    def packaging_rules(self) -> dict:
        return self._config.get("packaging", {})

    @property
    def commercial_settings(self) -> dict:
        return self._config.get("commercial", {})

    @property
    def llm_settings(self) -> dict:
        return self._config.get("llm", {})

    def reload(self):
        """Reload configuration from file."""
        self._config = self._load_config()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.setup_directories()
    return settings


@lru_cache
def get_rules() -> RulesConfig:
    """Get cached rules configuration."""
    return RulesConfig()
