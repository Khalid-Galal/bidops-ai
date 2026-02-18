"""Base model and shared enums for SQLAlchemy models."""

import enum

from sqlalchemy.orm import DeclarativeBase


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
