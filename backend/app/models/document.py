"""Document and DocumentChunk models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import DocumentCategory, DocumentStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Document(Base, TimestampMixin):
    """Document model for storing parsed document information."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # File information
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, xlsx, etc.
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Extracted content
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Document metadata extracted during parsing
    # { "title": ..., "author": ..., "creation_date": ..., etc. }
    doc_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Classification
    category: Mapped[DocumentCategory] = mapped_column(
        Enum(DocumentCategory), default=DocumentCategory.UNKNOWN
    )
    category_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Language detection
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # en, ar, etc.

    # Versioning (for addenda handling)
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Vector store reference
    vector_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of Qdrant point IDs

    # Timestamps
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    superseded_by: Mapped[Optional["Document"]] = relationship(
        remote_side=[id], foreign_keys=[superseded_by_id]
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename}>"


class DocumentChunk(Base):
    """Document chunk for vector embeddings."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Chunk information
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    # Page reference (if applicable)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Vector store reference
    vector_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Metadata for retrieval
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk {self.document_id}:{self.chunk_index}>"
