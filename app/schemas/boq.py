"""Schemas for BOQ parse results and item listing."""

from __future__ import annotations

from pydantic import BaseModel


class BOQItemResponse(BaseModel):
    id: int
    line_number: str | None
    section: str | None
    description: str
    unit: str | None
    quantity: float | None
    trade_category: str | None
    classification_confidence: float | None
    requires_review: bool

    model_config = {"from_attributes": True}


class BOQParseResult(BaseModel):
    project_id: int
    total: int
    classified: int
    uncategorized: int
    by_trade: dict[str, int]
