"""Base model classes and enums."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class ProjectStatus(enum.Enum):
    """Project lifecycle status."""

    DRAFT = "draft"
    INGESTING = "ingesting"
    READY = "ready"
    PACKAGING = "packaging"
    BIDDING = "bidding"
    EVALUATING = "evaluating"
    PRICING = "pricing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DocumentStatus(enum.Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DocumentCategory(enum.Enum):
    """Document classification category."""

    ITT = "itt"  # Invitation to Tender
    SPECS = "specs"  # Technical Specifications
    BOQ = "boq"  # Bill of Quantities
    DRAWINGS = "drawings"  # Architectural/Engineering Drawings
    CONTRACT = "contract"  # Contract Documents
    ADDENDUM = "addendum"  # Addenda/Amendments
    CORRESPONDENCE = "correspondence"  # Letters, Emails
    SCHEDULE = "schedule"  # Project Schedule
    HSE = "hse"  # Health, Safety, Environment
    GENERAL = "general"  # Other documents
    UNKNOWN = "unknown"


class PackageStatus(enum.Enum):
    """Package lifecycle status."""

    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    OFFERS_RECEIVED = "offers_received"
    EVALUATED = "evaluated"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class OfferStatus(enum.Enum):
    """Supplier offer status."""

    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    CLARIFICATION_SENT = "clarification_sent"
    CLARIFICATION_RECEIVED = "clarification_received"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    SELECTED = "selected"
    REJECTED = "rejected"


class EmailType(enum.Enum):
    """Email type classification."""

    RFQ = "rfq"  # Request for Quotation
    CLARIFICATION = "clarification"
    REMINDER = "reminder"
    AWARD = "award"
    REJECTION = "rejection"
    GENERAL = "general"


class EmailStatus(enum.Enum):
    """Email sending status."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class UserRole(enum.Enum):
    """User role for access control."""

    ADMIN = "admin"
    TENDER_MANAGER = "tender_manager"
    ESTIMATOR = "estimator"
    VIEWER = "viewer"


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
