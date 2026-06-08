"""Base model and shared enums for SQLAlchemy models."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class ProjectStatus(str, enum.Enum):
    """Status of a project through its lifecycle."""

    DRAFT = "draft"
    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"


class DocumentStatus(str, enum.Enum):
    """Status of a document through the parsing pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCategory(str, enum.Enum):
    """Classification category of a tender document."""

    ITT = "itt"
    SPECS = "specs"
    BOQ = "boq"
    DRAWINGS = "drawings"
    CONTRACT = "contract"
    ADDENDUM = "addendum"
    CORRESPONDENCE = "correspondence"
    SCHEDULE = "schedule"
    HSE = "hse"
    GENERAL = "general"
    UNKNOWN = "unknown"


class PackageStatus(str, enum.Enum):
    """Status of a procurement package through its lifecycle."""

    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    OFFERS_RECEIVED = "offers_received"
    EVALUATED = "evaluated"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class OfferStatus(str, enum.Enum):
    """Status of a supplier offer through evaluation."""

    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    CLARIFICATION_SENT = "clarification_sent"
    CLARIFICATION_RECEIVED = "clarification_received"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    SELECTED = "selected"
    REJECTED = "rejected"


class EmailType(str, enum.Enum):
    """Type of an outbound/inbound email communication."""

    RFQ = "rfq"
    CLARIFICATION = "clarification"
    REMINDER = "reminder"
    AWARD = "award"
    REJECTION = "rejection"
    GENERAL = "general"


class EmailStatus(str, enum.Enum):
    """Delivery status of an email."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class UserRole(str, enum.Enum):
    """Authorization role assigned to a user."""

    ADMIN = "admin"
    TENDER_MANAGER = "tender_manager"
    ESTIMATOR = "estimator"
    VIEWER = "viewer"


class TimestampMixin:
    """Mixin providing created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
