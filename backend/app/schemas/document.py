"""Document schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.base import DocumentCategory, DocumentStatus


class DocumentResponse(BaseModel):
    """Document response schema."""

    id: int
    project_id: int
    filename: str
    file_path: str
    file_type: str
    file_size: int
    content_hash: str
    status: DocumentStatus
    error_message: Optional[str]
    processing_time_ms: Optional[int]
    page_count: Optional[int]
    metadata: Optional[dict]
    category: DocumentCategory
    category_confidence: Optional[float]
    language: Optional[str]
    is_superseded: bool
    version: int
    indexed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Simplified document for list view."""

    id: int
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    category: DocumentCategory
    page_count: Optional[int]
    indexed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentSearchRequest(BaseModel):
    """Document semantic search request."""

    query: str = Field(min_length=1, max_length=1000)
    project_id: Optional[int] = None
    categories: Optional[list[DocumentCategory]] = None
    limit: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)


class DocumentSearchResult(BaseModel):
    """Single search result."""

    document_id: int
    filename: str
    chunk_text: str
    page_number: Optional[int]
    score: float
    metadata: Optional[dict]


class DocumentContentResponse(BaseModel):
    """Document content response."""

    id: int
    filename: str
    extracted_text: Optional[str]
    page_count: Optional[int]
    metadata: Optional[dict]


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""

    id: int
    filename: str
    status: DocumentStatus
    message: str
