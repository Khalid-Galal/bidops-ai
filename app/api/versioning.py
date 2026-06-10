"""Document versioning API: analyze (classify + dedup + supersede) and manual
supersede control."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.schemas.document import DocumentResponse
from app.services.versioning.versioning_service import VersioningService

router = APIRouter(tags=["versioning"])


class AnalyzeResult(BaseModel):
    project_id: int
    documents: int
    duplicates: int
    superseded: int
    by_category: dict[str, int]


class SupersedeRequest(BaseModel):
    superseded_by_id: int | None = None
    reason: str | None = None
    undo: bool = False


@router.post("/projects/{project_id}/documents/analyze", response_model=AnalyzeResult)
async def analyze_documents(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> AnalyzeResult:
    """Classify all documents, mark exact duplicates and older revisions."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await VersioningService().analyze(db, project_id)
    return AnalyzeResult(**result)


@router.patch("/documents/{document_id}/supersede", response_model=DocumentResponse)
async def supersede_document(
    document_id: int, payload: SupersedeRequest, db: AsyncSession = Depends(get_db)
) -> DocumentResponse:
    """Manually mark (or unmark with undo=true) a document as superseded —
    for cross-document addenda judgment the filename heuristic cannot make."""
    svc = VersioningService()
    if payload.undo:
        doc = await svc.unmark_superseded(db, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        return DocumentResponse.model_validate(doc)

    target = await db.get(Document, document_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    if payload.superseded_by_id is not None:
        if payload.superseded_by_id == document_id:
            raise HTTPException(
                status_code=422, detail="A document cannot supersede itself."
            )
        replacement = await db.get(Document, payload.superseded_by_id)
        if replacement is None or replacement.project_id != target.project_id:
            raise HTTPException(
                status_code=422,
                detail="superseded_by_id must be a document in the same project.",
            )

    doc = await svc.mark_superseded(
        db, document_id,
        superseded_by_id=payload.superseded_by_id,
        reason=payload.reason or "manually superseded",
    )
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return DocumentResponse.model_validate(doc)
