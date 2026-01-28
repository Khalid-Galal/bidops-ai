"""Email log model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import EmailStatus, EmailType, TimestampMixin

if TYPE_CHECKING:
    from app.models.package import Package
    from app.models.supplier import Supplier


class EmailLog(Base, TimestampMixin):
    """Email log for tracking sent communications."""

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # References
    package_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    offer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supplier_offers.id", ondelete="SET NULL"), nullable=True
    )

    # Email type and status
    email_type: Mapped[EmailType] = mapped_column(Enum(EmailType), nullable=False)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.DRAFT
    )

    # Recipients
    to_addresses: Mapped[list] = mapped_column(JSON, nullable=False)  # List of email addresses
    cc_addresses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    bcc_addresses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Email content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Attachments
    attachments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{ "name": ..., "path": ..., "size": ... }]
    total_attachment_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # bytes

    # Sending details
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # External references
    message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracking
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    email_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    package: Mapped[Optional["Package"]] = relationship(back_populates="email_logs")
    supplier: Mapped[Optional["Supplier"]] = relationship()

    def __repr__(self) -> str:
        return f"<EmailLog {self.id}: {self.subject[:50]}>"

    @property
    def is_sent(self) -> bool:
        """Check if email was sent."""
        return self.status in [EmailStatus.SENT, EmailStatus.DELIVERED]
