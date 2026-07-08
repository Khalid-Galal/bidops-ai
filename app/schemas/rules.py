"""Typed Pydantic models for the configurable business-rules system.

Mirrors config/rules.default.json. Every section has defaults so RulesConfig()
constructs a complete, valid config without any file present.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    """Base for all rules sections: reject unknown keys instead of silently
    dropping typos (extra='ignore' is Pydantic's default)."""

    model_config = ConfigDict(extra="forbid")


class ScoringWeights(_StrictModel):
    technical_compliance: float = 0.30
    price: float = 0.35
    delivery_time: float = 0.15
    payment_terms: float = 0.10
    supplier_rating: float = 0.10


class ScoringThresholds(_StrictModel):
    excellent: float = 90
    good: float = 75
    acceptable: float = 60
    poor: float = 40


class Scoring(_StrictModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    thresholds: ScoringThresholds = Field(default_factory=ScoringThresholds)


class Packaging(_StrictModel):
    max_items_per_package: int = 100
    trade_categories: dict[str, list[str]] = Field(default_factory=dict)


class EmailSubjectFormats(_StrictModel):
    rfq: str = "[{project_code}] RFQ - {package_name}"
    clarification: str = "[{project_code}] Clarification Request - {supplier_name}"
    reminder: str = "[{project_code}] Reminder - {package_name}"


class EmailRules(_StrictModel):
    from_address: str = ""
    reply_to: str = ""
    default_language: str = "en"
    attachment_size_limit_mb: int = 25
    subject_formats: EmailSubjectFormats = Field(default_factory=EmailSubjectFormats)


class Naming(_StrictModel):
    package_code_format: str = "PKG-{project_code}-{trade_abbr}-{seq:03d}"
    trade_abbreviations: dict[str, str] = Field(default_factory=dict)


class Markup(_StrictModel):
    profit: float = 0.10
    overhead: float = 0.08
    contingency: float = 0.05
    risk: float = 0.03


class Commercial(_StrictModel):
    currency: str = "USD"
    vat_rate: float = 0.0
    default_validity_days: int = 90
    default_payment_terms: str = "Net 30"
    markup: Markup = Field(default_factory=Markup)


class Measurement(_StrictModel):
    quantity_tolerance: float = 0.05
    unit_mappings: dict[str, str] = Field(default_factory=dict)


class Compliance(_StrictModel):
    required_offer_fields: list[str] = Field(
        default_factory=lambda: ["total_price", "validity_period", "delivery_time"]
    )


class DurationBasedRole(_StrictModel):
    monthly_rate: float = 0.0


class Indirects(_StrictModel):
    percentage_based: dict[str, float] = Field(default_factory=dict)
    duration_based: dict[str, DurationBasedRole] = Field(default_factory=dict)
    location_factors: dict[str, float] = Field(
        default_factory=lambda: {"default": 1.0, "remote": 1.15}
    )


class Classification(_StrictModel):
    """Keyword → document-category mapping. Dict order = match precedence."""

    document_categories: dict[str, list[str]] = Field(default_factory=dict)


class RulesConfig(_StrictModel):
    """Complete business-rules configuration. All sections default-constructible."""

    scoring: Scoring = Field(default_factory=Scoring)
    classification: Classification = Field(default_factory=Classification)
    packaging: Packaging = Field(default_factory=Packaging)
    email: EmailRules = Field(default_factory=EmailRules)
    naming: Naming = Field(default_factory=Naming)
    commercial: Commercial = Field(default_factory=Commercial)
    measurement: Measurement = Field(default_factory=Measurement)
    compliance: Compliance = Field(default_factory=Compliance)
    indirects: Indirects = Field(default_factory=Indirects)
