"""Pricing API: populate BOQ from offers, summarize with markups, report gaps,
manual overrides, and formula-preserving client-template population."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.models.boq import BOQItem
from app.models.project import Project
from app.schemas.pricing import (
    BOQItemPriceResponse,
    GapsReport,
    ItemPriceUpdate,
    PricePopulationResult,
    PricingSummary,
)
from app.services.pricing.pricing_service import PricingService
from app.services.pricing.template_writer import populate_template

router = APIRouter(tags=["pricing"])

# Cap inbound template uploads (consistent with app/api/suppliers.py and the
# Phase 9/10 fix — never read an unbounded body fully into memory).
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/offers/{offer_id}/populate-prices", response_model=PricePopulationResult)
async def populate_prices(
    offer_id: int,
    db: AsyncSession = Depends(get_db),
) -> PricePopulationResult:
    try:
        result = await PricingService().populate_from_offer(db, offer_id)
    except ValueError as exc:
        # "not found" -> 404; business-rule violations -> 409
        msg = str(exc)
        status = 404 if "not found" in msg.lower() else 409
        raise HTTPException(status_code=status, detail=msg) from exc
    return PricePopulationResult(**result)


@router.get("/projects/{project_id}/pricing/summary", response_model=PricingSummary)
async def pricing_summary(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> PricingSummary:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return PricingSummary(**await PricingService().pricing_summary(db, project_id))


@router.get("/projects/{project_id}/pricing/gaps", response_model=GapsReport)
async def pricing_gaps(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> GapsReport:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return GapsReport(**await PricingService().gaps_report(db, project_id))


@router.patch("/boq-items/{item_id}/price", response_model=BOQItemPriceResponse)
async def update_item_price(
    item_id: int, payload: ItemPriceUpdate, db: AsyncSession = Depends(get_db)
) -> BOQItemPriceResponse:
    item = await PricingService().update_item_price(
        db, item_id, payload.unit_rate, notes=payload.notes
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"BOQ item {item_id} not found")
    return BOQItemPriceResponse.model_validate(item)


@router.post("/projects/{project_id}/pricing/populate-template")
async def populate_client_template(
    project_id: int,
    file: UploadFile = File(...),
    rate_column: int | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    rows = (
        await db.execute(
            select(BOQItem.client_row_index, BOQItem.unit_rate).where(
                BOQItem.project_id == project_id,
                BOQItem.unit_rate.is_not(None),
                BOQItem.client_row_index.is_not(None),
                BOQItem.is_excluded.is_(False),
            )
        )
    ).all()
    row_rates = {int(idx): float(rate) for idx, rate in rows}
    if not row_rates:
        raise HTTPException(
            status_code=409,
            detail="No priced BOQ items with a client row mapping; populate prices first.",
        )

    suffix = Path(file.filename or "template.xlsx").suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as src_tmp:
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
        populate_template(src_path, out_path, row_rates, rate_column=rate_column)
    except ValueError as exc:
        Path(src_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _cleanup() -> None:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)

    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"priced_boq_project_{project_id}.xlsx",
        background=BackgroundTask(_cleanup),
    )
