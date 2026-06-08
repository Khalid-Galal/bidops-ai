"""Email log model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, EmailStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.package import Package
    from app.models.supplier import Supplier


class EmailLog(Base, TimestampMixin):
    """Email log for tracking sent communications."""

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # References
    package_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("packages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    offer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("supplier_offers.id", ondelete="SET NULL"), nullable=True
    )

    # Email type and status (stored as enum value strings per root convention)
    email_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=EmailStatus.DRAFT.value)

    # Recipients
    to: Mapped[list] = mapped_column("to_addresses", JSON, nullable=False)  # List of email addresses
    cc: Mapped[list | None] = mapped_column("cc_addresses", JSON, nullable=True)
    bcc: Mapped[list | None] = mapped_column("bcc_addresses", JSON, nullable=True)

    # Email content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Attachments
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{ "name": ..., "path": ..., "size": ... }]
    total_attachment_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes

    # Sending details
    # Intentionally nullable: a draft email may not have a sender assigned yet.
    from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # External references
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracking
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    email_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    package: Mapped[Package | None] = relationship(back_populates="email_logs")
    supplier: Mapped[Supplier | None] = relationship()

    def __repr__(self) -> str:
        return f"<EmailLog {self.id}: {self.subject[:50]}>"

    @property
    def is_sent(self) -> bool:
        """Check if email was sent."""
        return self.status in (EmailStatus.SENT.value, EmailStatus.DELIVERED.value)
