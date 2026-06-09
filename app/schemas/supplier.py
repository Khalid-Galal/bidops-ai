"""Schemas for supplier CRUD, search, and Excel import."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str
    emails: list[str] = Field(default_factory=list)
    trade_categories: list[str] = Field(default_factory=list)
    name_ar: str | None = None
    code: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    region: str | None = None
    country: str | None = None
    rating: float | None = None
    preferred_language: str | None = None
    preferred_format: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    """All fields optional; only provided fields are updated."""

    name: str | None = None
    emails: list[str] | None = None
    trade_categories: list[str] | None = None
    name_ar: str | None = None
    code: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    region: str | None = None
    country: str | None = None
    rating: float | None = None
    preferred_language: str | None = None
    preferred_format: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    name_ar: str | None = None
    code: str | None = None
    emails: list[str] = Field(default_factory=list)
    phone: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    trade_categories: list[str] = Field(default_factory=list)
    region: str | None = None
    country: str | None = None
    rating: float | None = None
    preferred_language: str | None = None
    is_active: bool = True
    is_blacklisted: bool = False
    total_rfqs_sent: int = 0
    total_offers_received: int = 0

    model_config = {"from_attributes": True}


class BlacklistRequest(BaseModel):
    reason: str


class SupplierImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    total_errors: int
