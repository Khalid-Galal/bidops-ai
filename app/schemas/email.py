"""Schemas for RFQ creation, email drafts, and the email log."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RFQCreateRequest(BaseModel):
    supplier_ids: list[int]
    language: str | None = None  # "en" | "ar"; default per supplier/rules
    custom_message: str | None = None


class EmailUpdateRequest(BaseModel):
    """Edit a draft before sending. Only provided fields change."""

    subject: str | None = None
    body_html: str | None = None
    to: list[str] | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    reply_to: str | None = None


class EmailLogResponse(BaseModel):
    id: int
    package_id: int | None = None
    supplier_id: int | None = None
    offer_id: int | None = None
    email_type: str
    status: str
    to: list[str] = Field(default_factory=list)
    cc: list[str] | None = None
    bcc: list[str] | None = None
    subject: str
    body_html: str
    body_text: str | None = None
    attachments: list[dict] | None = None
    total_attachment_size: int | None = None
    from_address: str | None = None
    reply_to: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None

    model_config = {"from_attributes": True}


class RFQCreateResult(BaseModel):
    package_id: int
    drafts_created: int
    email_ids: list[int]
    skipped: list[str] = Field(default_factory=list)  # reasons, e.g. "no email on supplier 4"


class EmailSendResult(BaseModel):
    email_id: int
    status: str
    message_id: str | None = None
    error: str | None = None


class SuggestedSupplierResponse(BaseModel):
    id: int
    name: str
    emails: list[str] = Field(default_factory=list)
    trade_categories: list[str] = Field(default_factory=list)
    rating: float | None = None

    model_config = {"from_attributes": True}
