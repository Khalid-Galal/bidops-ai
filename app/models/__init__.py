"""SQLAlchemy models for BidOps AI.

Note: the dead auth cluster (User, Organization, AuditLog, UserRole) was
removed here (2026-07). No destructive migration was added to drop the
now-orphaned `users`/`organizations`/`audit_logs` tables or the
`suppliers.organization_id` column on existing DBs - leaving them is
harmless and avoids risky DDL against live data.
"""

from app.models.base import (
    Base,
    DocumentCategory,
    DocumentStatus,
    EmailStatus,
    EmailType,
    OfferStatus,
    PackageStatus,
    ProjectStatus,
    TimestampMixin,
)
from app.models.boq import BOQItem
from app.models.document import Document
from app.models.email import EmailLog
from app.models.historical import HistoricalPrice
from app.models.package import Package, PackageDocument
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer

__all__ = [
    "BOQItem",
    "Base",
    "Document",
    "DocumentCategory",
    "DocumentStatus",
    "EmailLog",
    "EmailStatus",
    "EmailType",
    "HistoricalPrice",
    "OfferStatus",
    "Package",
    "PackageDocument",
    "PackageStatus",
    "Project",
    "ProjectStatus",
    "Supplier",
    "SupplierOffer",
    "TimestampMixin",
]
