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


class LinkedDocumentResponse(BaseModel):
    document_id: int
    filename: str
    relevance_score: float | None
    relevance_reason: str | None
    excerpt: str | None


class PackageDetailResponse(PackageResponse):
    items: list[BOQItemResponse] = []
    linked_documents: list[LinkedDocumentResponse] = []


class PackagingResult(BaseModel):
    project_id: int
    packages_created: int
    items_assigned: int
    items_unassigned: int
    by_trade: dict[str, int]


class DocumentLinkResult(BaseModel):
    project_id: int
    packages: int
    links_created: int


class PackageExportResult(BaseModel):
    project_id: int
    packages_exported: int
    register_path: str
    briefs_pdf: int
