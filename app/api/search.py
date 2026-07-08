"""Search API endpoint for hybrid keyword/semantic document search.

Exposes a GET endpoint that accepts a query, search mode, and result
limit. The endpoint validates the project exists, delegates to the
HybridSearchService, and returns structured results with source metadata
for citation linking.

Routes:
    GET /api/projects/{project_id}/search?q=...&mode=hybrid&limit=10
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.search import SearchResponse, SearchResultItem
from app.services.accessors import get_search_service as _get_search_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{project_id}/search",
    tags=["search"],
)


@router.get("", response_model=SearchResponse)
async def search_documents(
    project_id: int,
    q: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Search query text",
    ),
    mode: str = Query(
        "hybrid",
        pattern="^(hybrid|semantic|keyword)$",
        description="Search mode: hybrid, semantic, or keyword",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Maximum results to return",
    ),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search documents within a project by keyword, meaning, or both.

    Supports three search modes:
    - **hybrid** (default): Combines BM25 keyword and semantic vector
      search using Reciprocal Rank Fusion for best relevance.
    - **semantic**: Only vector similarity search (finds conceptually
      related content, even across languages).
    - **keyword**: Only BM25 keyword matching (finds exact terms).

    Arabic queries are automatically normalized (diacritics removed,
    alef/taa-marbuta unified) to match the normalized index.

    Args:
        project_id: ID of the project to search within.
        q: Search query text (1-500 characters).
        mode: Search mode (hybrid/semantic/keyword).
        limit: Maximum number of results (1-50, default 10).
        db: Database session (injected by FastAPI).

    Returns:
        SearchResponse with query, mode, total_results count, and ranked
        results list with source metadata for each match.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists.
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found",
        )

    search_service = _get_search_service()

    try:
        search_results = search_service.search(
            project_id=project_id,
            query=q,
            top_k=limit,
            mode=mode,
        )
    except Exception as exc:
        # Handle ChromaDB collection not existing (no documents indexed yet)
        # or any other search infrastructure error gracefully.
        logger.warning(
            "Search failed for project %d: %s",
            project_id,
            exc,
        )
        search_results = []

    # Convert SearchResult dataclass objects to Pydantic schema.
    result_items = [
        SearchResultItem(
            chunk_id=r.chunk_id,
            text=r.text,
            score=round(r.score, 6),
            document_id=r.document_id,
            page_number=r.page_number,
            language=r.language,
            filename=r.filename,
            chunk_type=r.chunk_type,
            section_name=r.section_name,
        )
        for r in search_results
    ]

    return SearchResponse(
        query=q,
        mode=mode,
        total_results=len(result_items),
        results=result_items,
    )
