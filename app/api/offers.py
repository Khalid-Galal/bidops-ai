"""Offers API: ingest, manual entry, AI extraction/compliance, scoring,
comparison (JSON + Excel), selection, and clarification drafts."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.models.package import Package
from app.models.supplier import Supplier
from app.schemas.email import EmailLogResponse
from app.schemas.offer import (
    ClarificationRequest,
    ComparisonResponse,
    OfferCommercialUpdate,
    OfferDetailResponse,
    OfferResponse,
    ScorePackageResult,
)
from app.services.email.rfq_service import RFQService
from app.services.offer.comparison_export import export_comparison_excel
from app.services.offer.offer_extractor import LLMUnavailable, OfferExtractor
from app.services.offer.offer_service import OfferService
from app.services.offer.scoring_service import ScoringService

router = APIRouter(tags=["offers"])

# Cap offer-ingest uploads to avoid unbounded reads into memory/disk.
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


async def _require_package(db: AsyncSession, project_id: int, package_id: int) -> Package:
    package = await db.get(Package, package_id)
    if package is None or package.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    return package


async def _detail(db: AsyncSession, offer) -> OfferDetailResponse:
    supplier = await db.get(Supplier, offer.supplier_id)
    base = OfferResponse.model_validate(offer)
    return OfferDetailResponse(
        **base.model_dump(),
        supplier_name=supplier.name if supplier else None,
        vat_included=offer.vat_included,
        exclusions=offer.exclusions,
        deviations=offer.deviations,
        missing_items=offer.missing_items,
        clarifications_needed=offer.clarifications_needed,
        compliance_analysis=offer.compliance_analysis,
        line_items=offer.line_items,
        evaluator_notes=offer.evaluator_notes,
        recommendation=offer.recommendation,
        missing_required_fields=OfferService().missing_required_fields(offer),
    )


def _safe_filename(name: str | None) -> str:
    return Path(name or "offer").name or "offer"


@router.post(
    "/projects/{project_id}/packages/{package_id}/offers",
    response_model=OfferResponse,
    status_code=201,
)
async def ingest_offer(
    project_id: int,
    package_id: int,
    supplier_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> OfferResponse:
    await _require_package(db, project_id, package_id)
    if await db.get(Supplier, supplier_id) is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    dest = Path("data") / "offers" / f"pkg_{package_id}" / f"sup_{supplier_id}"
    dest.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for upload in files:
        # uuid prefix guarantees uniqueness across offers and within one request
        # (same-named files no longer overwrite each other on disk).
        safe = f"{uuid.uuid4().hex}_{_safe_filename(upload.filename)}"
        target = dest / safe
        total = 0
        with open(target, "wb") as out:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail="Upload exceeds the maximum allowed size",
                    )
                out.write(chunk)
        saved.append(str(target))
    offer = await OfferService().create_offer(db, package_id, supplier_id, saved)
    return OfferResponse.model_validate(offer)


@router.get(
    "/projects/{project_id}/packages/{package_id}/offers",
    response_model=list[OfferResponse],
)
async def list_offers(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> list[OfferResponse]:
    await _require_package(db, project_id, package_id)
    offers = await OfferService().list_offers(db, package_id)
    return [OfferResponse.model_validate(o) for o in offers]


@router.post(
    "/projects/{project_id}/packages/{package_id}/offers/score",
    response_model=ScorePackageResult,
)
async def score_offers(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> ScorePackageResult:
    await _require_package(db, project_id, package_id)
    return ScorePackageResult(**await ScoringService().score_package(db, package_id))


@router.get(
    "/projects/{project_id}/packages/{package_id}/offers/comparison",
    response_model=ComparisonResponse,
)
async def comparison(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> ComparisonResponse:
    await _require_package(db, project_id, package_id)
    return ComparisonResponse(**await ScoringService().compare(db, package_id))


@router.get("/projects/{project_id}/packages/{package_id}/offers/comparison.xlsx")
async def comparison_xlsx(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
):
    await _require_package(db, project_id, package_id)
    data = await ScoringService().compare(db, package_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        out = tmp.name
    export_comparison_excel(data, out)
    return FileResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"comparison_package_{package_id}.xlsx",
        background=BackgroundTask(lambda: Path(out).unlink(missing_ok=True)),
    )


@router.get("/offers/{offer_id}", response_model=OfferDetailResponse)
async def get_offer(offer_id: int, db: AsyncSession = Depends(get_db)) -> OfferDetailResponse:
    offer = await OfferService().get_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return await _detail(db, offer)


@router.patch("/offers/{offer_id}", response_model=OfferDetailResponse)
async def update_offer(
    offer_id: int, payload: OfferCommercialUpdate, db: AsyncSession = Depends(get_db)
) -> OfferDetailResponse:
    offer = await OfferService().update_commercial(
        db, offer_id, **payload.model_dump(exclude_unset=True)
    )
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/extract", response_model=OfferDetailResponse)
async def extract_offer(offer_id: int, db: AsyncSession = Depends(get_db)) -> OfferDetailResponse:
    try:
        await OfferExtractor().extract_offer(db, offer_id)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    offer = await OfferService().get_offer(db, offer_id)
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/check-compliance", response_model=OfferDetailResponse)
async def check_compliance(offer_id: int, db: AsyncSession = Depends(get_db)) -> OfferDetailResponse:
    try:
        await OfferExtractor().check_compliance(db, offer_id)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    offer = await OfferService().get_offer(db, offer_id)
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/select", response_model=OfferDetailResponse)
async def select_offer(
    offer_id: int, payload: dict | None = None, db: AsyncSession = Depends(get_db)
) -> OfferDetailResponse:
    notes = (payload or {}).get("notes")
    offer = await OfferService().select_offer(db, offer_id, notes=notes)
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/clarification", response_model=EmailLogResponse, status_code=201)
async def create_clarification(
    offer_id: int, payload: ClarificationRequest, db: AsyncSession = Depends(get_db)
) -> EmailLogResponse:
    try:
        draft = await RFQService().create_clarification_drafts(
            db, offer_id, items=payload.items, language=payload.language,
            response_days=payload.response_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EmailLogResponse.model_validate(draft)
