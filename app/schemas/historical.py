"""Schemas for the historical-learning corpus, suggestions, import, feedback."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HistoricalPriceCreate(BaseModel):
    description: str
    rate: float
    unit: str | None = None
    currency: str | None = None
    trade_category: str | None = None
    description_ar: str | None = None
    source: str | None = None  # defaults to "manual" in the service


class HistoricalPriceResponse(BaseModel):
    id: int
    description: str
    unit: str | None = None
    rate: float
    currency: str | None = None
    trade_category: str | None = None
    source: str
    source_project_id: int | None = None
    recorded_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestionMatch(BaseModel):
    historical_id: int
    description: str
    unit: str | None = None
    rate: float
    currency: str | None = None
    source: str
    source_project_id: int | None = None
    similarity: float


class PriceBenchmark(BaseModel):
    count: int
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    median: float | None = None
    suggested_rate: float | None = None
    currency: str | None = None


class PriceSuggestion(BaseModel):
    query: str
    trade: str | None = None
    benchmark: PriceBenchmark
    matches: list[SuggestionMatch] = Field(default_factory=list)


class ItemSuggestion(BaseModel):
    boq_item_id: int
    line_number: str | None = None
    description: str
    suggestion: PriceSuggestion


class ProjectSuggestions(BaseModel):
    project_id: int
    suggestions: list[ItemSuggestion] = Field(default_factory=list)


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    total_errors: int


class IndexResult(BaseModel):
    project_id: int
    indexed: int


class FeedbackRequest(BaseModel):
    description: str
    accepted_rate: float
    unit: str | None = None
    currency: str | None = None
    trade_category: str | None = None
