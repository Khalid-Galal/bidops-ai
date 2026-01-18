"""AI Extraction endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.auth.permissions import Permission, check_permission
from app.models import Project
from app.services.extraction_service import ExtractionService

router = APIRouter()


# ============================================
# Request/Response Schemas
# ============================================

class ExtractSummaryRequest(BaseModel):
    """Request to extract project summary."""
    force_refresh: bool = Field(default=False, description="Force re-extraction")


class ExtractSummaryResponse(BaseModel):
    """Project summary extraction response."""
    project_id: int
    summary: dict
    fields_extracted: int
    low_confidence_fields: list[str]
    message: str


class GenerateChecklistRequest(BaseModel):
    """Request to generate checklist."""
    force_refresh: bool = Field(default=False, description="Force re-generation")


class ChecklistResponse(BaseModel):
    """Checklist generation response."""
    project_id: int
    requirements: list[dict]
    total_count: int
    mandatory_count: int
    categories: dict[str, int]
    message: str


class ClassifyDocumentResponse(BaseModel):
    """Document classification response."""
    document_id: int
    category: str
    confidence: float
    reasoning: str


class SearchRequest(BaseModel):
    """Semantic search request."""
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResponse(BaseModel):
    """Search with AI answer response."""
    answer: str
    sources: list[dict]
    confidence: float


class KeyDatesResponse(BaseModel):
    """Key dates extraction response."""
    project_id: int
    dates: list[dict]
    count: int


# ============================================
# Endpoints
# ============================================

@router.post(
    "/projects/{project_id}/extract-summary",
    response_model=ExtractSummaryResponse,
)
async def extract_project_summary(
    project_id: int,
    request: ExtractSummaryRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ExtractSummaryResponse:
    """Extract structured project summary from tender documents.

    Uses AI to analyze project documents and extract:
    - Project identification (name, owner, location)
    - Key dates (submission, site visit, clarifications)
    - Commercial terms (bonds, payments, retention)
    - Contract conditions
    - And more...

    Each field includes confidence score and source citations.
    """
    # Check permission
    if not check_permission(current_user.role, Permission.PROJECT_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        service = ExtractionService()
        summary = await service.extract_project_summary(
            project_id=project_id,
            force_refresh=request.force_refresh,
        )

        # Count fields and low confidence items
        fields_extracted = sum(
            1 for v in summary.values()
            if isinstance(v, dict) and v.get("value") is not None
        )

        low_confidence = [
            k for k, v in summary.items()
            if isinstance(v, dict) and v.get("requires_review", False)
        ]

        return ExtractSummaryResponse(
            project_id=project_id,
            summary=summary,
            fields_extracted=fields_extracted,
            low_confidence_fields=low_confidence,
            message="Summary extracted successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


@router.post(
    "/projects/{project_id}/generate-checklist",
    response_model=ChecklistResponse,
)
async def generate_requirements_checklist(
    project_id: int,
    request: GenerateChecklistRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ChecklistResponse:
    """Generate requirements checklist from tender documents.

    Analyzes ITT, specifications, and contract documents to extract
    all requirements, obligations, and conditions that must be met.

    Categories include:
    - SUBMISSION: Document submission requirements
    - QUALIFICATION: Pre-qualification requirements
    - TECHNICAL: Technical specifications
    - COMMERCIAL: Pricing and payment requirements
    - LEGAL: Legal and contractual requirements
    - HSE: Health, Safety, Environment
    - BONDS: Bond and guarantee requirements
    """
    # Check permission
    if not check_permission(current_user.role, Permission.PROJECT_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        service = ExtractionService()
        checklist = await service.generate_checklist(
            project_id=project_id,
            force_refresh=request.force_refresh,
        )

        # Calculate statistics
        categories = {}
        mandatory_count = 0

        for item in checklist:
            cat = item.get("category", "GENERAL")
            categories[cat] = categories.get(cat, 0) + 1
            if item.get("mandatory", True):
                mandatory_count += 1

        return ChecklistResponse(
            project_id=project_id,
            requirements=checklist,
            total_count=len(checklist),
            mandatory_count=mandatory_count,
            categories=categories,
            message="Checklist generated successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )


@router.post(
    "/documents/{document_id}/classify",
    response_model=ClassifyDocumentResponse,
)
async def classify_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ClassifyDocumentResponse:
    """Classify a document into a category using AI.

    Categories:
    - ITT: Invitation to Tender
    - SPECS: Technical Specifications
    - BOQ: Bill of Quantities
    - DRAWINGS: Drawings and Plans
    - CONTRACT: Contract Documents
    - ADDENDUM: Addenda/Amendments
    - HSE: Health, Safety, Environment
    - SCHEDULE: Project Schedule
    - GENERAL: Other
    """
    try:
        service = ExtractionService()
        result = await service.classify_document(document_id=document_id)

        return ClassifyDocumentResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}",
        )


@router.post(
    "/projects/{project_id}/search",
    response_model=SearchResponse,
)
async def search_project_documents(
    project_id: int,
    request: SearchRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SearchResponse:
    """Search project documents with AI-generated answer.

    Performs semantic search across all indexed documents and
    uses AI to generate a comprehensive answer with citations.

    Example queries:
    - "What is the submission deadline?"
    - "What are the tender bond requirements?"
    - "List the HSE requirements"
    """
    # Check permission
    if not check_permission(current_user.role, Permission.PROJECT_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        service = ExtractionService()
        result = await service.search_with_context(
            query=request.query,
            project_id=project_id,
            top_k=request.top_k,
        )

        return SearchResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/key-dates",
    response_model=KeyDatesResponse,
)
async def extract_key_dates(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> KeyDatesResponse:
    """Extract all key dates from project documents.

    Searches for and extracts dates related to:
    - Submission deadlines
    - Site visits
    - Clarification deadlines
    - Award dates
    - Commencement dates
    - Completion dates
    - Milestones
    """
    # Check permission
    if not check_permission(current_user.role, Permission.PROJECT_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        service = ExtractionService()
        dates = await service.extract_key_dates(project_id=project_id)

        return KeyDatesResponse(
            project_id=project_id,
            dates=dates,
            count=len(dates),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


@router.get("/projects/{project_id}/summary")
async def get_project_summary(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get cached project summary.

    Returns the previously extracted summary.
    Use POST /extract-summary to generate or refresh.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project.summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not yet extracted. Use POST /extract-summary first.",
        )

    return {
        "project_id": project_id,
        "summary": project.summary,
    }


@router.get("/projects/{project_id}/checklist")
async def get_project_checklist(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = Query(None, description="Filter by category"),
    mandatory_only: bool = Query(False, description="Show only mandatory items"),
) -> dict:
    """Get cached requirements checklist.

    Returns the previously generated checklist.
    Use POST /generate-checklist to generate or refresh.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project.checklist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checklist not yet generated. Use POST /generate-checklist first.",
        )

    checklist = project.checklist

    # Apply filters
    if category:
        checklist = [
            item for item in checklist
            if item.get("category", "").upper() == category.upper()
        ]

    if mandatory_only:
        checklist = [
            item for item in checklist
            if item.get("mandatory", True)
        ]

    return {
        "project_id": project_id,
        "requirements": checklist,
        "total_count": len(checklist),
    }
