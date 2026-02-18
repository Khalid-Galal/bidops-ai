"""Pydantic schemas for Project API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class ProjectResponse(BaseModel):
    """Schema for project API responses."""

    id: int
    name: str
    description: str | None
    status: str
    total_documents: int
    processed_documents: int
    failed_documents: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    """Schema for listing projects."""

    projects: list[ProjectResponse]
