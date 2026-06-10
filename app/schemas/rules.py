"""Typed Pydantic models for the configurable business-rules system.

Mirrors config/rules.default.json. Every section has defaults so RulesConfig()
constructs a complete, valid config without any file present.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    technical_compliance: float = 0.30
    price: float = 0.35
    delivery_time: float = 0.15
    payment_terms: float = 0.10
    supplier_rating: float = 0.10


class ScoringThresholds(BaseModel):
    excellent: float = 90
    good: float = 75
    acceptable: float = 60
    poor: float = 40


class Scoring(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    thresholds: ScoringThresholds = Field(default_factory=ScoringThresholds)


class Keywords(BaseModel):
    mandatory: list[str] = Field(default_factory=list)
    deadline: list[str] = Field(default_factory=list)
    bond: list[str] = Field(default_factory=list)
    payment: list[str] = Field(default_factory=list)


class Packaging(BaseModel):
    min_items_per_package: int = 5
    max_items_per_package: int = 100
    grouping_criteria: list[str] = Field(
        default_factory=lambda: ["trade_category", "spec_section"]
    )
    trade_categories: dict[str, list[str]] = Field(default_factory=dict)


class EmailSubjectFormats(BaseModel):
    rfq: str = "[{project_code}] RFQ - {package_name}"
    clarification: str = "[{project_code}] Clarification Request - {supplier_name}"
    reminder: str = "[{project_code}] Reminder - {package_name}"


class EmailRules(BaseModel):
    provider: str = "smtp"
    draft_only: bool = True
    from_address: str = ""
    reply_to: str = ""
    default_language: str = "en"
    attachment_size_limit_mb: int = 25
    subject_formats: EmailSubjectFormats = Field(default_factory=EmailSubjectFormats)


class Naming(BaseModel):
    project_code_format: str = "PRJ-{year}-{seq:04d}"
    package_code_format: str = "PKG-{project_code}-{trade_abbr}-{seq:03d}"
    offer_folder_format: str = "{package_code}/{supplier_name}"
    document_naming: str = "{project_code}_{category}_{date}_{seq}"
    trade_abbreviations: dict[str, str] = Field(default_factory=dict)


class Markup(BaseModel):
    profit: float = 0.10
    overhead: float = 0.08
    contingency: float = 0.05
    risk: float = 0.03


class Commercial(BaseModel):
    currency: str = "USD"
    vat_rate: float = 0.0
    default_validity_days: int = 90
    default_payment_terms: str = "Net 30"
    markup: Markup = Field(default_factory=Markup)


class Measurement(BaseModel):
    contract_type: str = "lumpsum"
    quantity_tolerance: float = 0.05
    unit_mappings: dict[str, str] = Field(default_factory=dict)


class Compliance(BaseModel):
    required_offer_fields: list[str] = Field(
        default_factory=lambda: ["total_price", "validity_period", "delivery_time"]
    )
    non_compliance_triggers: list[str] = Field(default_factory=list)


class DurationBasedRole(BaseModel):
    monthly_rate: float = 0.0


class Indirects(BaseModel):
    percentage_based: dict[str, float] = Field(default_factory=dict)
    duration_based: dict[str, DurationBasedRole] = Field(default_factory=dict)
    location_factors: dict[str, float] = Field(
        default_factory=lambda: {"default": 1.0, "remote": 1.15}
    )


class Classification(BaseModel):
    """Keyword → document-category mapping. Dict order = match precedence."""

    document_categories: dict[str, list[str]] = Field(default_factory=dict)


class RulesConfig(BaseModel):
    """Complete business-rules configuration. All sections default-constructible."""

    scoring: Scoring = Field(default_factory=Scoring)
    keywords: Keywords = Field(default_factory=Keywords)
    classification: Classification = Field(default_factory=Classification)
    packaging: Packaging = Field(default_factory=Packaging)
    email: EmailRules = Field(default_factory=EmailRules)
    naming: Naming = Field(default_factory=Naming)
    commercial: Commercial = Field(default_factory=Commercial)
    measurement: Measurement = Field(default_factory=Measurement)
    compliance: Compliance = Field(default_factory=Compliance)
    indirects: Indirects = Field(default_factory=Indirects)
