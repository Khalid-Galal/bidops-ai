"""Supplier and Offer schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr

from app.models.base import OfferStatus, EmailStatus, EmailType


# ============================================================================
# Supplier Schemas
# ============================================================================


class SupplierBase(BaseModel):
    """Base supplier schema."""

    name: str = Field(..., max_length=255)
    emails: list[str] = Field(default_factory=list)
    trade_categories: list[str] = Field(default_factory=list)


class SupplierCreate(SupplierBase):
    """Schema for creating a supplier."""

    name_ar: Optional[str] = Field(None, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    fax: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    website: Optional[str] = Field(None, max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    preferred_language: Optional[str] = Field("en", max_length=10)
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier."""

    name: Optional[str] = Field(None, max_length=255)
    name_ar: Optional[str] = Field(None, max_length=255)
    emails: Optional[list[str]] = None
    trade_categories: Optional[list[str]] = None
    phone: Optional[str] = Field(None, max_length=50)
    fax: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    website: Optional[str] = Field(None, max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    rating: Optional[float] = Field(None, ge=0, le=5)
    preferred_language: Optional[str] = Field(None, max_length=10)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierListResponse(BaseModel):
    """Supplier list item response."""

    id: int
    name: str
    code: Optional[str] = None
    emails: list[str]
    trade_categories: list[str]
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    rating: Optional[float] = None
    is_active: bool = True
    is_blacklisted: bool = False
    total_rfqs_sent: int = 0
    total_offers_received: int = 0

    model_config = {"from_attributes": True}


class SupplierResponse(SupplierListResponse):
    """Full supplier response."""

    name_ar: Optional[str] = None
    fax: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    total_awards: int = 0
    average_response_days: Optional[float] = None
    preferred_language: Optional[str] = None
    preferred_format: Optional[str] = None
    notes: Optional[str] = None
    blacklist_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierImportRequest(BaseModel):
    """Request to import suppliers from Excel."""

    file_path: str
    update_existing: bool = False


class SupplierImportResponse(BaseModel):
    """Response from supplier import."""

    imported: int
    updated: int
    skipped: int
    total_errors: int
    errors: list[str] = []


class SupplierBlacklistRequest(BaseModel):
    """Request to blacklist a supplier."""

    reason: str = Field(..., min_length=10)


class SupplierPerformanceResponse(BaseModel):
    """Supplier performance statistics."""

    total_rfqs_sent: int
    total_offers_received: int
    total_awards: int
    response_rate: float


# ============================================================================
# Offer Schemas
# ============================================================================


class OfferCreate(BaseModel):
    """Schema for creating an offer."""

    supplier_id: int
    file_paths: list[str]


class OfferUpdate(BaseModel):
    """Schema for updating an offer."""

    status: Optional[OfferStatus] = None
    total_price: Optional[float] = None
    currency: Optional[str] = Field(None, max_length=10)
    validity_days: Optional[int] = None
    payment_terms: Optional[str] = None
    delivery_weeks: Optional[int] = None
    technical_score: Optional[float] = Field(None, ge=0, le=100)
    evaluator_notes: Optional[str] = None


class OfferListResponse(BaseModel):
    """Offer list item response."""

    id: int
    package_id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    status: OfferStatus
    total_price: Optional[float] = None
    currency: Optional[str] = None
    commercial_score: Optional[float] = None
    technical_score: Optional[float] = None
    overall_score: Optional[float] = None
    rank: Optional[int] = None
    received_at: datetime

    model_config = {"from_attributes": True}


class OfferResponse(OfferListResponse):
    """Full offer response."""

    vat_included: Optional[bool] = None
    vat_amount: Optional[float] = None
    validity_days: Optional[int] = None
    validity_date: Optional[datetime] = None
    payment_terms: Optional[str] = None
    delivery_weeks: Optional[int] = None
    delivery_terms: Optional[str] = None
    exclusions: Optional[list] = None
    deviations: Optional[list] = None
    missing_items: Optional[list] = None
    clarifications_needed: Optional[list] = None
    compliance_analysis: Optional[dict] = None
    line_items: Optional[list] = None
    file_paths: list[str] = []
    evaluator_notes: Optional[str] = None
    recommendation: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OfferExtractResponse(BaseModel):
    """Response from offer data extraction."""

    total_price: Optional[dict] = None
    validity_days: Optional[int] = None
    payment_terms: Optional[str] = None
    delivery_weeks: Optional[int] = None
    line_items: list[dict] = []
    exclusions: list[str] = []
    deviations: list[dict] = []


class OfferComplianceResponse(BaseModel):
    """Response from compliance check."""

    overall_compliance: str
    compliance_score: float
    requirements_analysis: list[dict] = []
    critical_issues: list[str] = []
    clarifications_needed: list[str] = []
    recommendation: Optional[str] = None


class OfferEvaluateRequest(BaseModel):
    """Request to evaluate an offer."""

    technical_score: Optional[float] = Field(None, ge=0, le=100)
    commercial_weight: float = Field(0.6, ge=0, le=1)
    technical_weight: float = Field(0.4, ge=0, le=1)


class OfferEvaluateResponse(BaseModel):
    """Response from offer evaluation."""

    offer_id: int
    commercial_score: float
    technical_score: float
    overall_score: float


class OfferRankResponse(BaseModel):
    """Ranked offer item."""

    rank: int
    offer_id: int
    supplier_name: str
    total_price: Optional[float] = None
    currency: Optional[str] = None
    commercial_score: Optional[float] = None
    technical_score: Optional[float] = None
    overall_score: Optional[float] = None
    status: str


class OfferComparisonResponse(BaseModel):
    """Offer comparison summary."""

    package_id: int
    package_name: str
    total_boq_items: int
    total_offers: int
    evaluated_offers: int
    price_statistics: dict
    offers: list[dict]


class OfferSelectRequest(BaseModel):
    """Request to select an offer."""

    notes: Optional[str] = None


# ============================================================================
# Email Schemas
# ============================================================================


class EmailCreateRequest(BaseModel):
    """Request to create an email."""

    supplier_id: int
    attachments: Optional[list[str]] = None
    custom_message: Optional[str] = None


class EmailSendRequest(BaseModel):
    """Request to send an email."""

    email_id: int


class EmailBulkSendRequest(BaseModel):
    """Request to send bulk RFQ emails."""

    supplier_ids: list[int]
    attachments: Optional[list[str]] = None


class EmailBulkSendResponse(BaseModel):
    """Response from bulk email send."""

    total: int
    created: int
    sent: int
    failed: int
    errors: list[dict] = []


class EmailLogResponse(BaseModel):
    """Email log response."""

    id: int
    package_id: Optional[int] = None
    supplier_id: Optional[int] = None
    email_type: EmailType
    status: EmailStatus
    to_addresses: list[str]
    subject: str
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClarificationEmailRequest(BaseModel):
    """Request to create clarification email."""

    clarification_items: list[str]
    response_days: int = Field(3, ge=1, le=14)
