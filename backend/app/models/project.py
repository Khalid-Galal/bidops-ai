"""Project model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import ProjectStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import Organization, User
    from app.models.document import Document
    from app.models.boq import BOQItem
    from app.models.package import Package


class Project(Base, TimestampMixin):
    """Project model representing a tender/bid."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source paths
    folder_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    cloud_link: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Status
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.DRAFT
    )

    # Extracted summary with evidence (JSON)
    # Structure: { "field_name": { "value": ..., "confidence": 0.9, "evidence": [...] } }
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Generated requirements checklist (JSON)
    # Structure: [{ "category": ..., "item": ..., "source": ..., "mandatory": true, ... }]
    checklist: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Project configuration (JSON)
    # Scoring weights, currency, language, etc.
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Key dates extracted from documents
    submission_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    site_visit_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    clarification_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Document counts (for quick access)
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    indexed_documents: Mapped[int] = mapped_column(Integer, default=0)
    failed_documents: Mapped[int] = mapped_column(Integer, default=0)

    # Ownership
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Soft delete
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="projects")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    boq_items: Mapped[list["BOQItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    packages: Mapped[list["Package"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"

    @property
    def indexing_progress(self) -> float:
        """Calculate indexing progress percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.indexed_documents / self.total_documents) * 100
