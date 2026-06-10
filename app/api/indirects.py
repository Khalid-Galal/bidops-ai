"""Indirects API: the project indirect-cost breakdown and the full project
cost rollup (direct -> indirects -> markups -> VAT -> grand total)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from zipfile import BadZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.models.project import Project
from app.schemas.indirects import IndirectsResult, ProjectCostSummary
from app.services.indirects.indirects_service import IndirectsService
from app.services.indirects.indirects_template import populate_indirects_template
from app.services.pricing.pricing_service import PricingService

router = APIRouter(tags=["indirects"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_TEMPLATE_EXT = {".xlsx"}


@router.get("/projects/{project_id}/indirects", response_model=IndirectsResult)
async def get_indirects(
    project_id: int,
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> IndirectsResult:
    """Indirect-cost breakdown only (percentage-of-direct + duration-based staff +
    location factor). For the full priced rollup use GET .../cost-summary."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await IndirectsService().indirects_result(
        db, project_id, duration_months=duration_months, location=location
    )
    return IndirectsResult(**result)


@router.get("/projects/{project_id}/cost-summary", response_model=ProjectCostSummary)
async def get_cost_summary(
    project_id: int,
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> ProjectCostSummary:
    """Full project cost rollup: direct cost -> + indirects -> + markups -> + VAT.

    NOTE: this marks up the **direct + indirects** base, so its grand_total is
    intentionally larger than GET .../pricing/summary (which marks up the direct
    cost only). Use this endpoint for the complete project total.
    """
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await IndirectsService().project_cost_summary(
        db, project_id, duration_months=duration_months, location=location
    )
    return ProjectCostSummary(**result)


@router.post("/projects/{project_id}/indirects/populate-template")
async def populate_indirects_client_template(
    project_id: int,
    file: UploadFile = File(...),
    amount_column: int | None = Form(default=None),
    label_column: int | None = Form(default=None),
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
):
    """Fill the client's indirects template with computed amounts (formula-
    preserving). Components come from rules.indirects applied to the project's
    priced direct cost."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_TEMPLATE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported template type; upload .xlsx")

    summary = await PricingService().pricing_summary(db, project_id)
    ind = IndirectsService().compute(
        summary["cost_subtotal"], duration_months=duration_months, location=location
    )
    components = {
        **ind["percentage_based"],
        **ind["duration_based"],
        "total_indirects": ind["total_indirects"],
    }
    components = {k: v for k, v in components.items() if v}
    if not components:
        raise HTTPException(
            status_code=409,
            detail="No indirect amounts to populate; price the BOQ or set duration_months.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as src_tmp:
        src_path = src_tmp.name
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                src_tmp.close()
                Path(src_path).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail="Upload exceeds the maximum allowed size"
                )
            src_tmp.write(chunk)
    out_path = src_path + ".populated.xlsx"
    try:
        populate_indirects_template(
            src_path, out_path, components,
            amount_column=amount_column, label_column=label_column,
        )
    except (ValueError, BadZipFile, InvalidFileException, KeyError) as exc:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
        raise

    def _cleanup() -> None:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)

    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"indirects_project_{project_id}.xlsx",
        background=BackgroundTask(_cleanup),
    )
