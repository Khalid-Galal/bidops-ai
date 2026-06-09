"""Schemas for BOQ pricing: population results, summary, gaps, manual update."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PricePopulationResult(BaseModel):
    offer_id: int
    package_id: int
    items_populated: int
    items_needs_review: int
    items_unmatched: int
    total_value: float
    currency: str | None = None


class TradePricing(BaseModel):
    trade: str
    count: int
    total: float
    percentage: float


class MarkupBreakdown(BaseModel):
    overhead: float
    profit: float
    contingency: float
    risk: float
    markup_total: float


class PricingSummary(BaseModel):
    project_id: int
    currency: str
    total_items: int
    priced_items: int
    unpriced_items: int
    completion_rate: float
    cost_subtotal: float
    markups: MarkupBreakdown
    selling_before_vat: float
    vat_rate: float
    vat_amount: float
    grand_total: float = Field(
        description=(
            "Selling total for the DIRECT cost only (markups on the direct subtotal "
            "+ VAT). Excludes indirects — see GET .../cost-summary for the full "
            "project total that marks up direct+indirects."
        )
    )
    by_trade: list[TradePricing] = Field(default_factory=list)


class GapItem(BaseModel):
    id: int
    line_number: str | None = None
    description: str
    trade_category: str | None = None
    reason: str


class GapsReport(BaseModel):
    project_id: int
    unpriced_count: int
    needs_review_count: int
    excluded_count: int
    unpriced: list[GapItem] = Field(default_factory=list)
    needs_review: list[GapItem] = Field(default_factory=list)
    excluded: list[GapItem] = Field(default_factory=list)


class ItemPriceUpdate(BaseModel):
    unit_rate: float
    notes: str | None = None


class BOQItemPriceResponse(BaseModel):
    id: int
    line_number: str | None = None
    description: str
    unit: str | None = None
    quantity: float
    unit_rate: float | None = None
    total_price: float | None = None
    currency: str | None = None
    mapping_confidence: float | None = None
    requires_review: bool
    is_excluded: bool

    model_config = {"from_attributes": True}
