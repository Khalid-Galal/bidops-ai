"""Checklist API endpoints for triggering and retrieving requirements checklist extraction.

Routes:
    POST  /api/projects/{project_id}/checklist       - Trigger full checklist extraction pipeline
    GET   /api/projects/{project_id}/checklist       - Retrieve stored checklist results
    PATCH /api/projects/{project_id}/checklist/items - Update individual checklist items
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.database import async_session_factory
from app.models.project import Project
from app.schemas.checklist import ChecklistResponse, RequirementsChecklist


class ChecklistItemUpdate(BaseModel):
    """Request body for updating a single checklist item."""

    category: str
    index: int
    updates: dict

logger = logging.getLogger(__name__)

# Lazy singleton for ChecklistService (same pattern as extraction API).
_checklist_service = None


def _get_checklist_service():
    """Get or create the ChecklistService singleton.

    Lazily initializes all required services (embedding, search, LLM,
    citation verifier) on first call. Validates Gemini API key is set.

    Returns:
        The ChecklistService singleton instance.

    Raises:
        HTTPException: 500 if BIDOPS_GEMINI_API_KEY is not configured.
    """
    global _checklist_service
    if _checklist_service is None:
        settings = get_settings()
        if not settings.gemini_key_list():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="BIDOPS_GEMINI_API_KEY (or BIDOPS_GEMINI_API_KEYS) not configured. Set it in .env or environment.",
            )
        from app.services.extraction.checklist_service import ChecklistService
        from app.services.extraction.citation_verifier import CitationVerifier
        from app.services.indexing.embedding_service import EmbeddingService
        from app.services.llm.gemini_service import GeminiService
        from app.services.search.hybrid_search import HybridSearchService

        embedding_svc = EmbeddingService(
            persist_dir=settings.chroma_persist_dir,
            model_name=settings.embedding_model,
        )
        search_svc = HybridSearchService(embedding_service=embedding_svc)
        llm_svc = GeminiService(
            api_keys=settings.gemini_key_list(),
            model=settings.gemini_model,
        )
        verifier = CitationVerifier(
            model_name=settings.nli_model,
            confidence_high=settings.confidence_high_threshold,
            confidence_low=settings.confidence_low_threshold,
            review_threshold=settings.review_threshold,
        )
        _checklist_service = ChecklistService(
            search_service=search_svc,
            llm_service=llm_svc,
            citation_verifier=verifier,
        )
    return _checklist_service


def _count_checklist(checklist: RequirementsChecklist) -> tuple[int, int]:
    """Count total and review-requiring requirements in a checklist.

    Args:
        checklist: The RequirementsChecklist to count items for.

    Returns:
        Tuple of (total_requirements, requirements_requiring_review).
    """
    all_items = (
        checklist.requirements
        + checklist.submission_documents
        + checklist.eligibility_criteria
    )
    total_requirements = len(all_items)
    requirements_requiring_review = sum(
        1 for item in all_items if item.requires_review
    )
    return total_requirements, requirements_requiring_review


router = APIRouter(tags=["checklist"])


@router.post(
    "/projects/{project_id}/checklist",
    response_model=ChecklistResponse,
)
async def extract_project_checklist(project_id: int) -> ChecklistResponse:
    """Trigger full checklist extraction pipeline for a project.

    Runs per-category hybrid search retrieval, Gemini LLM extraction, NLI
    citation verification, semantic deduplication, and checklist assembly.
    Results are persisted to the project's checklist_json column.

    Args:
        project_id: Database ID of the project to extract.

    Returns:
        ChecklistResponse with status, checklist, and requirement counts.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 409 if checklist extraction already in progress.
        HTTPException: 500 on extraction failure.
    """
    # Verify project exists
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with id {project_id} not found",
            )
        # Prevent duplicate extraction
        if project.checklist_status == "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Checklist extraction already in progress for this project",
            )

    checklist_service = _get_checklist_service()

    try:
        checklist = await checklist_service.extract_and_persist_checklist(project_id)
        total_requirements, requirements_requiring_review = _count_checklist(checklist)

        return ChecklistResponse(
            project_id=project_id,
            status="completed",
            checklist=checklist,
            total_requirements=total_requirements,
            requirements_requiring_review=requirements_requiring_review,
        )
    except Exception as exc:
        logger.exception("Checklist extraction failed for project %d", project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checklist extraction failed: {exc}",
        ) from exc


@router.get(
    "/projects/{project_id}/checklist",
    response_model=ChecklistResponse,
)
async def get_checklist_result(project_id: int) -> ChecklistResponse:
    """Retrieve stored checklist extraction results for a project.

    Returns the previously extracted requirements checklist from the database
    without re-running extraction. Includes extraction status, checklist
    data, and requirement counts.

    Args:
        project_id: Database ID of the project.

    Returns:
        ChecklistResponse with current status and stored checklist.

    Raises:
        HTTPException: 404 if project not found.
    """
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with id {project_id} not found",
            )

        # Not started
        if project.checklist_status is None:
            return ChecklistResponse(
                project_id=project_id,
                status="not_started",
                checklist=None,
                total_requirements=0,
                requirements_requiring_review=0,
            )

        # In progress
        if project.checklist_status == "in_progress":
            return ChecklistResponse(
                project_id=project_id,
                status="in_progress",
                checklist=None,
                total_requirements=0,
                requirements_requiring_review=0,
            )

        # Completed with results
        if project.checklist_status == "completed" and project.checklist_json:
            checklist = RequirementsChecklist.model_validate_json(
                project.checklist_json
            )
            total_requirements, requirements_requiring_review = _count_checklist(
                checklist
            )
            return ChecklistResponse(
                project_id=project_id,
                status="completed",
                checklist=checklist,
                total_requirements=total_requirements,
                requirements_requiring_review=requirements_requiring_review,
            )

        # Failed
        return ChecklistResponse(
            project_id=project_id,
            status="failed",
            checklist=None,
            total_requirements=0,
            requirements_requiring_review=0,
        )


@router.patch("/projects/{project_id}/checklist/items")
async def update_checklist_item(
    project_id: int,
    update: ChecklistItemUpdate,
) -> dict:
    """Update a single checklist item within a category.

    Allows toggling the checked state or editing the requirement text
    for an individual item, identified by category and index.

    Args:
        project_id: Database ID of the project.
        update: The category, index, and fields to update.

    Returns:
        Success status with updated category and index.

    Raises:
        HTTPException: 404 if project not found, checklist not extracted,
            category missing, or index out of bounds.
    """
    valid_categories = {"requirements", "submission_documents", "eligibility_criteria"}
    if update.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{update.category}'. Must be one of: {', '.join(sorted(valid_categories))}",
        )

    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with id {project_id} not found",
            )
        if project.checklist_json is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No checklist data exists for this project",
            )

        checklist_data = json.loads(project.checklist_json)

        if update.category not in checklist_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category '{update.category}' not found in checklist data",
            )

        category_items = checklist_data[update.category]
        if update.index < 0 or update.index >= len(category_items):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Index {update.index} out of bounds for category '{update.category}' (length: {len(category_items)})",
            )

        category_items[update.index].update(update.updates)
        project.checklist_json = json.dumps(checklist_data, ensure_ascii=False)
        flag_modified(project, "checklist_json")
        await session.commit()

    return {
        "status": "updated",
        "category": update.category,
        "index": update.index,
    }
