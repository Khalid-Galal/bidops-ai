"""Extraction API endpoints for triggering and retrieving project summary extraction.

Routes:
    POST /api/projects/{project_id}/extract - Trigger full extraction pipeline
    GET  /api/projects/{project_id}/extract - Retrieve stored extraction results
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.database import async_session_factory
from app.models.project import Project
from app.schemas.extraction import ExtractionResponse, ProjectSummary

logger = logging.getLogger(__name__)

# Lazy singleton for ExtractionService (same pattern as search API).
_extraction_service = None


def _get_extraction_service():
    """Get or create the ExtractionService singleton.

    Lazily initializes all required services (embedding, search, LLM,
    citation verifier) on first call. Validates Gemini API key is set.

    Returns:
        The ExtractionService singleton instance.

    Raises:
        HTTPException: 500 if BIDOPS_GEMINI_API_KEY is not configured.
    """
    global _extraction_service
    if _extraction_service is None:
        settings = get_settings()
        if not settings.gemini_key_list():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="BIDOPS_GEMINI_API_KEY (or BIDOPS_GEMINI_API_KEYS) not configured. Set it in .env or environment.",
            )
        from app.services.extraction.citation_verifier import CitationVerifier
        from app.services.extraction.extraction_service import ExtractionService
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
        _extraction_service = ExtractionService(
            search_service=search_svc,
            llm_service=llm_svc,
            citation_verifier=verifier,
        )
    return _extraction_service


def _count_fields(summary: ProjectSummary) -> tuple[int, int]:
    """Count extracted and review-requiring fields in a ProjectSummary.

    Args:
        summary: The ProjectSummary to count fields for.

    Returns:
        Tuple of (fields_extracted, fields_requiring_review).
    """
    fields_extracted = 0
    fields_requiring_review = 0
    for field_data in summary.model_dump().values():
        if isinstance(field_data, dict):
            if field_data.get("value") is not None:
                fields_extracted += 1
            if field_data.get("requires_review", False):
                fields_requiring_review += 1
    return fields_extracted, fields_requiring_review


router = APIRouter(tags=["extraction"])


@router.post(
    "/projects/{project_id}/extract",
    response_model=ExtractionResponse,
)
async def extract_project_summary(project_id: int) -> ExtractionResponse:
    """Trigger full extraction pipeline for a project.

    Runs per-field hybrid search retrieval, Gemini LLM extraction, and
    NLI citation verification for all 13 summary fields. Results are
    persisted to the project's summary_json column.

    Args:
        project_id: Database ID of the project to extract.

    Returns:
        ExtractionResponse with status, summary, and field counts.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 409 if extraction already in progress.
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
        if project.extraction_status == "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Extraction already in progress for this project",
            )

    extraction_service = _get_extraction_service()

    try:
        summary = await extraction_service.extract_and_persist(project_id)
        fields_extracted, fields_requiring_review = _count_fields(summary)

        return ExtractionResponse(
            project_id=project_id,
            status="completed",
            summary=summary,
            fields_extracted=fields_extracted,
            fields_requiring_review=fields_requiring_review,
        )
    except Exception as exc:
        logger.exception("Extraction failed for project %d", project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {exc}",
        ) from exc


@router.get(
    "/projects/{project_id}/extract",
    response_model=ExtractionResponse,
)
async def get_extraction_result(project_id: int) -> ExtractionResponse:
    """Retrieve stored extraction results for a project.

    Returns the previously extracted project summary from the database
    without re-running extraction. Includes extraction status, summary
    data, and field counts.

    Args:
        project_id: Database ID of the project.

    Returns:
        ExtractionResponse with current status and stored summary.

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
        if project.extraction_status is None:
            return ExtractionResponse(
                project_id=project_id,
                status="not_started",
                summary=None,
                fields_extracted=0,
                fields_requiring_review=0,
            )

        # In progress
        if project.extraction_status == "in_progress":
            return ExtractionResponse(
                project_id=project_id,
                status="in_progress",
                summary=None,
                fields_extracted=0,
                fields_requiring_review=0,
            )

        # Completed with results
        if project.extraction_status == "completed" and project.summary_json:
            summary = ProjectSummary.model_validate_json(project.summary_json)
            fields_extracted, fields_requiring_review = _count_fields(summary)
            return ExtractionResponse(
                project_id=project_id,
                status="completed",
                summary=summary,
                fields_extracted=fields_extracted,
                fields_requiring_review=fields_requiring_review,
            )

        # Failed
        return ExtractionResponse(
            project_id=project_id,
            status="failed",
            summary=None,
            fields_extracted=0,
            fields_requiring_review=0,
        )
