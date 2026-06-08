"""Package and PackageDocument models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PackageStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.boq import BOQItem
    from app.models.document import Document
    from app.models.email import EmailLog
    from app.models.supplier import SupplierOffer


class Package(Base, TimestampMixin):
    """Package model for grouping BOQ items for procurement."""

    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Package identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., PKG-001-HVAC
    trade_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status (stored as enum value string per root convention)
    status: Mapped[str] = mapped_column(
        String(20), default=PackageStatus.DRAFT.value
    )

    # Submission details
    submission_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submission_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Package value estimates
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Folder path for package outputs
    folder_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Brief document path
    brief_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Supplier targeting (list of supplier IDs to send to)
    target_supplier_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Configuration
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Statistics
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    offers_received: Mapped[int] = mapped_column(Integer, default=0)
    offers_evaluated: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    items: Mapped[list[BOQItem]] = relationship(back_populates="package")
    offers: Mapped[list[SupplierOffer]] = relationship(back_populates="package")
    email_logs: Mapped[list[EmailLog]] = relationship(back_populates="package")
    linked_documents: Mapped[list[PackageDocument]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Package {self.code}: {self.name}>"


class PackageDocument(Base, TimestampMixin):
    """Link between Package and relevant Documents."""

    __tablename__ = "package_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relevance
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Specific sections/pages
    sections: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List of section references
    page_ranges: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [[1, 5], [10, 15]]

    # Excerpt for package brief
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether to include in package attachments
    include_in_package: Mapped[bool] = mapped_column(default=True)

    # Relationships
    package: Mapped[Package] = relationship(back_populates="linked_documents")
    document: Mapped[Document] = relationship()

    def __repr__(self) -> str:
        return f"<PackageDocument {self.package_id}:{self.document_id}>"
