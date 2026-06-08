"""BOQ (Bill of Quantities) Item model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.package import Package
    from app.models.supplier import SupplierOffer


class BOQItem(Base, TimestampMixin):
    """Bill of Quantities item model."""

    __tablename__ = "boq_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # BOQ reference
    line_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subsection: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Item details
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)  # Arabic description
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # Client reference (for mapping back to template)
    client_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Classification (AI-generated)
    trade_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    trade_subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Spec references (linked document sections)
    # [{ "document_id": 1, "section": "15.3", "page": 45 }, ...]
    spec_references: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Pricing (after offer selection)
    selected_offer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("supplier_offers.id", ondelete="SET NULL"), nullable=True
    )
    unit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Mapping status
    mapping_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    package: Mapped[Package | None] = relationship(back_populates="items")
    selected_offer: Mapped[SupplierOffer | None] = relationship()

    def __repr__(self) -> str:
        return f"<BOQItem {self.line_number}: {self.description[:50]}>"

    @property
    def full_reference(self) -> str:
        """Get full hierarchical reference."""
        parts = [p for p in [self.section, self.subsection, self.line_number] if p]
        return ".".join(parts)
