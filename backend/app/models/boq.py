"""BOQ (Bill of Quantities) Item model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.package import Package
    from app.models.supplier import SupplierOffer


class BOQItem(Base, TimestampMixin):
    """Bill of Quantities item model."""

    __tablename__ = "boq_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # BOQ reference
    line_number: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subsection: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Item details
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Arabic description
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # Client reference (for mapping back to template)
    client_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    client_row_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Classification (AI-generated)
    trade_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    trade_subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Spec references (linked document sections)
    # [{ "document_id": 1, "section": "15.3", "page": 45 }, ...]
    spec_references: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Pricing (after offer selection)
    selected_offer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supplier_offers.id", ondelete="SET NULL"), nullable=True
    )
    unit_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Mapping status
    mapping_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="boq_items")
    package: Mapped[Optional["Package"]] = relationship(back_populates="items")
    selected_offer: Mapped[Optional["SupplierOffer"]] = relationship()

    def __repr__(self) -> str:
        return f"<BOQItem {self.line_number}: {self.description[:50]}>"

    @property
    def full_reference(self) -> str:
        """Get full hierarchical reference."""
        parts = [p for p in [self.section, self.subsection, self.line_number] if p]
        return ".".join(parts)
