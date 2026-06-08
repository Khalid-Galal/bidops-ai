"""Schemas for package generation results and package views."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.boq import BOQItemResponse


class PackageResponse(BaseModel):
    id: int
    code: str
    name: str
    trade_category: str
    status: str
    total_items: int

    model_config = {"from_attributes": True}


class PackageDetailResponse(PackageResponse):
    items: list[BOQItemResponse] = []


class PackagingResult(BaseModel):
    project_id: int
    packages_created: int
    items_assigned: int
    items_unassigned: int
    by_trade: dict[str, int]
