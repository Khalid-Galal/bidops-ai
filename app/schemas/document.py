"""Pydantic schemas for Document API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Schema for document API responses."""

    id: int
    project_id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    page_count: int | None
    processing_time_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadResponse(BaseModel):
    """Schema for upload endpoint response."""

    task_id: str
    uploaded: int
    skipped: int
    filenames: list[str]


class ProgressEvent(BaseModel):
    """Schema for SSE progress events."""

    status: str
    total: int
    processed: int
    current_file: str
    errors: list[dict]
