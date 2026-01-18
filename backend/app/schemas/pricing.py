"""Pricing and export schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Pricing Schemas
# ============================================================================


class PricePopulateRequest(BaseModel):
    """Request to populate prices from an offer."""

    offer_id: int
    apply_markup: bool = False
    markup_percentage: Optional[float] = Field(None, ge=0, le=1)


class PricePopulateResponse(BaseModel):
    """Response from price population."""

    offer_id: int
    package_id: int
    items_populated: int
    items_skipped: int
    total_value: float
    currency: Optional[str] = None


class PackageTotalsResponse(BaseModel):
    """Package pricing totals."""

    package_id: int
    package_name: str
    total_items: int
    priced_items: int
    unpriced_items: int
    subtotal: float
    currency: str
    completion_rate: float


class ProjectTotalsResponse(BaseModel):
    """Project pricing totals."""

    project_id: int
    project_name: str
    total_packages: int
    total_items: int
    priced_items: int
    unpriced_items: int
    total_value: float
    by_trade: dict[str, dict]
    completion_rate: float


class ApplyMarkupRequest(BaseModel):
    """Request to apply markup to a package."""

    markup_percentage: float = Field(..., ge=0, le=1)
    only_unpriced: bool = False


class ApplyMarkupResponse(BaseModel):
    """Response from markup application."""

    package_id: int
    items_updated: int
    markup_applied: str


class PriceComparisonItem(BaseModel):
    """Price comparison for a single BOQ item."""

    id: int
    line_number: str
    description: str
    unit: str
    quantity: float
    prices: dict[str, dict]
    min_rate: Optional[float] = None
    max_rate: Optional[float] = None
    avg_rate: Optional[float] = None
    spread: Optional[float] = None


class PriceComparisonResponse(BaseModel):
    """Price comparison across offers."""

    package_id: int
    package_name: str
    boq_items: list[PriceComparisonItem]


class CostBreakdownTrade(BaseModel):
    """Cost breakdown for a trade."""

    trade: str
    count: int
    total: float
    percentage: float
    top_items: list[dict]


class CostBreakdownResponse(BaseModel):
    """Project cost breakdown."""

    project_id: int
    grand_total: float
    trades: list[CostBreakdownTrade]


class UpdateItemPriceRequest(BaseModel):
    """Request to update a single item price."""

    unit_rate: float = Field(..., ge=0)
    source: Optional[str] = None


class BulkPriceUpdate(BaseModel):
    """Single price update in bulk request."""

    item_id: int
    unit_rate: float = Field(..., ge=0)
    source: Optional[str] = None


class BulkPriceUpdateRequest(BaseModel):
    """Request to bulk update prices."""

    updates: list[BulkPriceUpdate]


class BulkPriceUpdateResponse(BaseModel):
    """Response from bulk price update."""

    updated: int
    failed: int
    errors: list[str] = []


class CopyPricesRequest(BaseModel):
    """Request to copy prices between packages."""

    source_package_id: int
    match_by: str = Field("description", pattern="^(description|line_number)$")


class CopyPricesResponse(BaseModel):
    """Response from copying prices."""

    source_package_id: int
    target_package_id: int
    items_copied: int
    total_target_items: int


# ============================================================================
# Export Schemas
# ============================================================================


class ExportBOQRequest(BaseModel):
    """Request to export priced BOQ."""

    output_path: Optional[str] = None
    include_breakdown: bool = True
    format_style: str = Field("standard", pattern="^(standard|detailed|summary)$")


class ExportBOQResponse(BaseModel):
    """Response from BOQ export."""

    file_path: str
    project_id: int
    format_style: str


class GenerateReportRequest(BaseModel):
    """Request to generate a report."""

    report_type: str = Field(..., pattern="^(pricing|status|evaluation)$")
    output_path: Optional[str] = None


class GenerateReportResponse(BaseModel):
    """Response from report generation."""

    file_path: str
    report_type: str
    project_id: Optional[int] = None
    package_id: Optional[int] = None


# ============================================================================
# Dashboard Schemas
# ============================================================================


class DashboardSummary(BaseModel):
    """Dashboard summary statistics."""

    total_packages: int
    total_items: int
    priced_items: int
    pricing_completion: float
    total_value: float
    total_offers: int


class DashboardResponse(BaseModel):
    """Dashboard statistics response."""

    project_id: int
    project_name: str
    project_status: str
    summary: DashboardSummary
    packages_by_status: dict[str, int]
    offers_by_status: dict[str, int]
    value_by_trade: dict[str, float]
