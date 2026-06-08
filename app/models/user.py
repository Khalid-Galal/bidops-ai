"""User and Organization models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UserRole

if TYPE_CHECKING:
    from app.models.audit import AuditLog


class Organization(Base, TimestampMixin):
    """Organization/Company model."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Contact info
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Settings (JSON)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    users: Mapped[list[User]] = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization {self.name}>"


class User(Base, TimestampMixin):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Role and permissions (stored as enum value string per root convention)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.VIEWER.value)

    # Organization
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="users")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
