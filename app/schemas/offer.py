"""Schemas for offer ingest, manual commercial entry, scoring, comparison, and
the LLM extraction/compliance response models used by OfferExtractor."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------
# LLM response models (passed to GeminiService.extract via instructor)
# ----------------------------------------------------------------------------


class OfferLineItem(BaseModel):
    description: str = Field(default="", description="Line item description, or empty if not found")
    unit: str | None = Field(default=None, description="Unit of measure, or null if not stated")
    quantity: float | None = Field(default=None, description="Quantity, or null if not stated")
    rate: float | None = Field(default=None, description="Unit rate/price, or null if not stated")
    total: float | None = Field(default=None, description="Line total, or null if not stated")


class OfferExtraction(BaseModel):
    """Commercial data extracted from a supplier's offer documents."""

    total_price: float | None = Field(
        default=None,
        description="Total offer price, or null if not found in the documents",
    )
    currency: str | None = Field(
        default=None,
        description="ISO or local currency code/symbol as it appears in the offer (e.g. USD, EGP, SAR), or null if not stated",
    )
    vat_included: bool | None = Field(
        default=None,
        description="Whether the total price includes VAT/tax; true if explicitly included, false if explicitly excluded/additional, null if not mentioned",
    )
    validity_days: int | None = Field(
        default=None,
        description="Offer validity period in days, or null if not stated",
    )
    payment_terms: str | None = Field(
        default=None,
        description="Payment terms as described in the offer, or null if not stated",
    )
    delivery_weeks: int | None = Field(
        default=None,
        description="Delivery/lead time in weeks, or null if not stated",
    )
    delivery_terms: str | None = Field(
        default=None,
        description="Delivery/shipment terms or incoterms as stated in the offer (e.g. FOB, CIF, DDP, 'delivered to site'), or null if not stated",
    )
    exclusions: list[str] = Field(
        default_factory=list,
        description="Explicit exclusions from scope stated in the offer",
    )
    deviations: list[str] = Field(
        default_factory=list,
        description="Explicit deviations from the tender requirements stated in the offer",
    )
    line_items: list[OfferLineItem] = Field(
        default_factory=list,
        description="Priced line items found in the offer",
    )


class ComplianceAnalysis(BaseModel):
    """Compliance of an offer against the tender checklist + package scope."""

    overall_compliance: Literal["COMPLIANT", "NON_COMPLIANT", "PARTIAL", "UNKNOWN"] = Field(
        default="UNKNOWN",
        description="Overall compliance verdict against the tender requirements",
    )
    compliance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Compliance score from 0 to 100",
    )
    missing_items: list[str] = Field(
        default_factory=list,
        description="Required items/documents that the offer does not address",
    )
    deviations: list[str] = Field(
        default_factory=list,
        description="Deviations from tender requirements found in the offer",
    )
    clarifications_needed: list[str] = Field(
        default_factory=list,
        description="Points that need clarification from the supplier",
    )
    notes: str = Field(
        default="",
        description="Brief explanation of the compliance assessment",
    )


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
    supplier_name: str | None = None
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
    missing_required_fields: list[str] = Field(default_factory=list)


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
    delivery_terms: str | None = None
    payment_terms: str | None = None
    vat_included: bool | None = None
    vat_amount: float | None = None
    commercial_score: float | None = None
    technical_score: float | None = None
    overall_score: float | None = None
    rank: int | None = None
    status: str
    exclusions: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
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
    # Loud flags for conditions that make the raw price_min/max/avg above (and
    # the per-offer ranking) unreliable at a glance: mixed currencies across
    # offers, or a mix of VAT-inclusive/VAT-exclusive/unstated pricing. Minimal
    # by design -- surfaced as text, not blocked or auto-converted.
    warnings: list[str] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    items: list[str] | None = None  # defaults to offer.clarifications_needed
    language: str | None = None
    response_days: int = 3
