"""Schemas for the indirects engine and the full project cost rollup."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.pricing import MarkupBreakdown


class IndirectsBreakdown(BaseModel):
    percentage_based: dict[str, float] = Field(default_factory=dict)  # component -> amount
    duration_based: dict[str, float] = Field(default_factory=dict)  # role -> amount
    duration_months: int
    location: str
    location_factor: float
    subtotal_before_location: float
    total_indirects: float


class IndirectsResult(BaseModel):
    project_id: int
    currency: str
    direct_cost: float
    indirects: IndirectsBreakdown


class ProjectCostSummary(BaseModel):
    project_id: int
    currency: str
    direct_cost: float
    indirects: IndirectsBreakdown
    total_cost_base: float  # direct + indirects (the markup base)
    markups: MarkupBreakdown
    selling_before_vat: float
    vat_rate: float
    vat_amount: float
    grand_total: float
