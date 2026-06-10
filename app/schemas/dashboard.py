"""Schema for the project status dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PackageCard(BaseModel):
    id: int
    code: str
    name: str
    trade_category: str
    status: str
    total_items: int
    offers_received: int
    offers_evaluated: int


class ProjectDashboard(BaseModel):
    project: dict
    documents: dict
    boq: dict
    packages: list[PackageCard] = Field(default_factory=list)
    package_status_counts: dict[str, int] = Field(default_factory=dict)
    suppliers: dict
    offers: dict
    emails: dict
    pricing: dict
    gaps: dict
    historical: dict
