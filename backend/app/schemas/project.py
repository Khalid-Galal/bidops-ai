"""Project schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.base import ProjectStatus


class EvidenceCitation(BaseModel):
    """Evidence citation for extracted data."""

    document: str = Field(description="Document filename")
    page: Optional[str] = Field(None, description="Page number or section")
    snippet: str = Field(description="Relevant text excerpt")


class ProjectSummaryField(BaseModel):
    """Single field in project summary with evidence."""

    value: Optional[Any] = Field(None, description="Extracted value")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    evidence: list[EvidenceCitation] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Full project summary with all extracted fields."""

    project_name: Optional[ProjectSummaryField] = None
    project_owner: Optional[ProjectSummaryField] = None
    main_contractor: Optional[ProjectSummaryField] = None
    location: Optional[ProjectSummaryField] = None
    submission_deadline: Optional[ProjectSummaryField] = None
    site_visit_date: Optional[ProjectSummaryField] = None
    scope_of_work: Optional[ProjectSummaryField] = None
    tender_bond: Optional[ProjectSummaryField] = None
    contract_type: Optional[ProjectSummaryField] = None
    contract_conditions: Optional[ProjectSummaryField] = None
    commercial_terms: Optional[ProjectSummaryField] = None
    sustainability: Optional[ProjectSummaryField] = None
    consultants: Optional[ProjectSummaryField] = None


class ChecklistItem(BaseModel):
    """Requirements checklist item."""

    id: int
    category: str  # Technical, Commercial, HSE, etc.
    requirement: str
    source_document: Optional[str] = None
    source_reference: Optional[str] = None  # Page/section
    mandatory: bool = True
    owner: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "open"  # open, in_progress, completed
    notes: Optional[str] = None


class ProjectCreate(BaseModel):
    """Project creation schema."""

    name: str = Field(min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    folder_path: Optional[str] = None
    cloud_link: Optional[str] = None
    config: Optional[dict] = None


class ProjectUpdate(BaseModel):
    """Project update schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    folder_path: Optional[str] = None
    cloud_link: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[ProjectStatus] = None
    submission_deadline: Optional[datetime] = None
    site_visit_date: Optional[datetime] = None
    clarification_deadline: Optional[datetime] = None


class ProjectResponse(BaseModel):
    """Project response schema."""

    id: int
    name: str
    code: Optional[str]
    description: Optional[str]
    folder_path: Optional[str]
    cloud_link: Optional[str]
    status: ProjectStatus
    summary: Optional[dict]
    checklist: Optional[list]
    config: Optional[dict]
    submission_deadline: Optional[datetime]
    site_visit_date: Optional[datetime]
    clarification_deadline: Optional[datetime]
    total_documents: int
    indexed_documents: int
    failed_documents: int
    organization_id: int
    created_by_id: int
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Simplified project for list view."""

    id: int
    name: str
    code: Optional[str]
    status: ProjectStatus
    total_documents: int
    indexed_documents: int
    submission_deadline: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectIngestRequest(BaseModel):
    """Request to start document ingestion."""

    folder_path: Optional[str] = None  # Override project folder
    force_reindex: bool = False  # Reindex already indexed documents


class ProjectIngestResponse(BaseModel):
    """Response after starting ingestion."""

    message: str
    task_id: str
    total_files: int
