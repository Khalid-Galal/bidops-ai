"""Schemas for offer ingest, manual commercial entry, scoring, comparison, and
the LLM extraction/compliance response models used by OfferExtractor."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------
# LLM response models (passed to GeminiService.extract via instructor)
# ----------------------------------------------------------------------------


class OfferLineItem(BaseModel):
    description: str = ""
    unit: str | None = None
    quantity: float | None = None
    rate: float | None = None
    total: float | None = None


class OfferExtraction(BaseModel):
    """Commercial data extracted from a supplier's offer documents."""

    total_price: float | None = None
    currency: str | None = None
    vat_included: bool | None = None
    validity_days: int | None = None
    payment_terms: str | None = None
    delivery_weeks: int | None = None
    exclusions: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    line_items: list[OfferLineItem] = Field(default_factory=list)


class ComplianceAnalysis(BaseModel):
    """Compliance of an offer against the tender checklist + package scope."""

    overall_compliance: str = "UNKNOWN"  # COMPLIANT | NON_COMPLIANT | PARTIAL | UNKNOWN
    compliance_score: float = 0.0  # 0-100
    missing_items: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    clarifications_needed: list[str] = Field(default_factory=list)
    notes: str = ""


# ----------------------------------------------------------------------------
# API request/response models
# ----------------------------------------------------------------------------


class OfferCommercialUpdate(BaseModel):
    """Manual entry/edit of offer fields (works with no LLM key)."""

    total_price: float | None = None
    currency: str | None = None
    vat_included: bool | None = None
    vat_amount: float | None = None
    validity_days: int | None = None
    payment_terms: str | None = None
    delivery_weeks: int | None = None
    delivery_terms: str | None = None
    technical_score: float | None = None  # manual technical sub-score (0-100)
    exclusions: list[str] | None = None
    deviations: list[str] | None = None
    line_items: list[dict] | None = None
    evaluator_notes: str | None = None


class OfferResponse(BaseModel):
    id: int
    package_id: int
    supplier_id: int
    status: str
    total_price: float | None = None
    currency: str | None = None
    validity_days: int | None = None
    delivery_weeks: int | None = None
    payment_terms: str | None = None
    commercial_score: float | None = None
    technical_score: float | None = None
    overall_score: float | None = None
    rank: int | None = None
    file_paths: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OfferDetailResponse(OfferResponse):
    supplier_name: str | None = None
    vat_included: bool | None = None
    exclusions: list | None = None
    deviations: list | None = None
    missing_items: list | None = None
    clarifications_needed: list | None = None
    compliance_analysis: dict | None = None
    line_items: list | None = None
    evaluator_notes: str | None = None
    recommendation: str | None = None


class OfferScore(BaseModel):
    offer_id: int
    supplier_name: str
    subscores: dict[str, float]
    overall_score: float
    rank: int
    band: str


class ScorePackageResult(BaseModel):
    package_id: int
    offers_scored: int
    weights: dict[str, float]
    ranking: list[OfferScore]


class ComparisonOffer(BaseModel):
    offer_id: int
    supplier_id: int
    supplier_name: str
    total_price: float | None = None
    currency: str | None = None
    validity_days: int | None = None
    delivery_weeks: int | None = None
    payment_terms: str | None = None
    commercial_score: float | None = None
    technical_score: float | None = None
    overall_score: float | None = None
    rank: int | None = None
    status: str
    exclusions_count: int = 0
    deviations_count: int = 0


class ComparisonResponse(BaseModel):
    package_id: int
    package_name: str
    total_offers: int
    evaluated_offers: int
    currency: str
    price_min: float | None = None
    price_max: float | None = None
    price_avg: float | None = None
    offers: list[ComparisonOffer] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    items: list[str] | None = None  # defaults to offer.clarifications_needed
    language: str | None = None
    response_days: int = 3
