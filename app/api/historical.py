"""Historical-learning API: corpus management, Excel import, project snapshot,
benchmark suggestions, and the correction-feedback loop."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.historical import (
    FeedbackRequest,
    HistoricalPriceCreate,
    HistoricalPriceResponse,
    ImportResult,
    IndexResult,
    PriceSuggestion,
    ProjectSuggestions,
)
from app.services.historical.historical_service import HistoricalService

router = APIRouter(tags=["historical"])

# Cap inbound rate-sheet uploads (consistent with suppliers/pricing).
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_EXT = {".xlsx"}


@router.post("/historical", response_model=HistoricalPriceResponse, status_code=201)
async def add_record(
    payload: HistoricalPriceCreate, db: AsyncSession = Depends(get_db)
) -> HistoricalPriceResponse:
    data = payload.model_dump(exclude_unset=True)
    source = data.pop("source", None) or "manual"
    rec = await HistoricalService().add(
        db,
        description=data.pop("description"),
        rate=data.pop("rate"),
        source=source,
        **data,
    )
    return HistoricalPriceResponse.model_validate(rec)


@router.get("/historical", response_model=list[HistoricalPriceResponse])
async def list_records(
    trade: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[HistoricalPriceResponse]:
    recs = await HistoricalService().list_records(db, trade=trade)
    return [HistoricalPriceResponse.model_validate(r) for r in recs]


@router.post("/historical/import", response_model=ImportResult)
async def import_rate_sheet(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file type; upload .xlsx")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                tmp.close()
                Path(tmp_path).unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Upload exceeds the maximum allowed size")
            tmp.write(chunk)
    try:
        result = await HistoricalService().import_excel(db, tmp_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return ImportResult(**result)


@router.post("/historical/feedback", response_model=HistoricalPriceResponse, status_code=201)
async def record_feedback(
    payload: FeedbackRequest, db: AsyncSession = Depends(get_db)
) -> HistoricalPriceResponse:
    rec = await HistoricalService().record_feedback(
        db,
        description=payload.description,
        accepted_rate=payload.accepted_rate,
        unit=payload.unit,
        currency=payload.currency,
        trade_category=payload.trade_category,
    )
    return HistoricalPriceResponse.model_validate(rec)


@router.get("/historical/suggest", response_model=PriceSuggestion)
async def suggest(
    description: str = Query(..., min_length=1),
    unit: str | None = Query(default=None),
    trade: str | None = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> PriceSuggestion:
    out = await HistoricalService().suggest(
        db, description, unit=unit, trade=trade, top_k=top_k
    )
    return PriceSuggestion(**out)


@router.post("/projects/{project_id}/historical/index", response_model=IndexResult)
async def index_project(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> IndexResult:
    try:
        result = await HistoricalService().index_project(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IndexResult(**result)


@router.get(
    "/projects/{project_id}/historical/suggestions", response_model=ProjectSuggestions
)
async def project_suggestions(
    project_id: int,
    only_unpriced: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> ProjectSuggestions:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    out = await HistoricalService().suggest_for_project(
        db, project_id, only_unpriced=only_unpriced
    )
    return ProjectSuggestions(**out)
