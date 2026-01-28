"""Supplier and SupplierOffer models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import OfferStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import Organization
    from app.models.package import Package


class Supplier(Base, TimestampMixin):
    """Supplier/Vendor model."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Arabic name
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Contact
    emails: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # List of email addresses
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Contact person
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Classification
    trade_categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # List of trades
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Rating and performance
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 1-5
    total_rfqs_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_offers_received: Mapped[int] = mapped_column(Integer, default=0)
    total_awards: Mapped[int] = mapped_column(Integer, default=0)
    average_response_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Preferences
    preferred_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # en, ar
    preferred_format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # pdf, excel
    max_attachment_size_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    offers: Mapped[list["SupplierOffer"]] = relationship(back_populates="supplier")

    def __repr__(self) -> str:
        return f"<Supplier {self.name}>"

    @property
    def response_rate(self) -> float:
        """Calculate response rate percentage."""
        if self.total_rfqs_sent == 0:
            return 0.0
        return (self.total_offers_received / self.total_rfqs_sent) * 100


class SupplierOffer(Base, TimestampMixin):
    """Supplier offer/quotation model."""

    __tablename__ = "supplier_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Status
    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus), default=OfferStatus.RECEIVED
    )

    # File references
    file_paths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # List of file paths

    # Commercial data (extracted)
    total_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    vat_included: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    vat_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Terms
    validity_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validity_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivery_weeks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Incoterms

    # Compliance analysis (AI-generated)
    exclusions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    deviations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    missing_items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    clarifications_needed: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Scoring
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-100
    commercial_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-100
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Weighted
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Full compliance analysis JSON
    compliance_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Line item pricing (parsed breakdown)
    # [{ "description": ..., "unit": ..., "qty": ..., "rate": ..., "total": ... }, ...]
    line_items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Evaluation notes
    evaluator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    package: Mapped["Package"] = relationship(back_populates="offers")
    supplier: Mapped["Supplier"] = relationship(back_populates="offers")

    def __repr__(self) -> str:
        return f"<SupplierOffer {self.supplier_id} for {self.package_id}>"

    @property
    def is_compliant(self) -> bool:
        """Check if offer is compliant."""
        return self.status in [OfferStatus.COMPLIANT, OfferStatus.SELECTED]
