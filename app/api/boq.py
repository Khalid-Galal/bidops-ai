"""BOQ API: parse an uploaded BOQ workbook and list parsed items."""

from __future__ import annotations

import tempfile
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.boq import BOQItemResponse, BOQParseResult
from app.services.boq.boq_service import BOQService

router = APIRouter(prefix="/projects/{project_id}/boq", tags=["boq"])

_ALLOWED = {".xlsx", ".xls"}


@router.post("/parse", response_model=BOQParseResult)
async def parse_boq(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> BOQParseResult:
    """Parse + classify + persist a BOQ workbook for a project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported BOQ file type: {ext}")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / (file.filename or "boq.xlsx")
        async with aiofiles.open(path, "wb") as out:
            await out.write(await file.read())
        summary = await BOQService().parse_and_store(db, project_id, str(path))

    return BOQParseResult(project_id=project_id, **summary)


@router.get("", response_model=list[BOQItemResponse])
async def list_boq(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[BOQItemResponse]:
    """List parsed BOQ items for a project, ordered by source row."""
    items = await BOQService().list_items(db, project_id)
    return [BOQItemResponse.model_validate(i) for i in items]
