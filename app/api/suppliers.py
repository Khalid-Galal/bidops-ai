"""Suppliers API: global supplier database (single-user) with Excel I/O."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.schemas.supplier import (
    BlacklistRequest,
    SupplierCreate,
    SupplierImportResult,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

# Cap supplier-import uploads to avoid unbounded reads into a temp file.
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreate, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    data = payload.model_dump(exclude_unset=True)
    supplier = await SupplierService().create(
        db,
        name=data.pop("name"),
        emails=data.pop("emails", []),
        trade_categories=data.pop("trade_categories", []),
        **data,
    )
    return SupplierResponse.model_validate(supplier)


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    query: str | None = Query(default=None),
    trade: str | None = Query(default=None),
    region: str | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    min_rating: float | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[SupplierResponse]:
    suppliers = await SupplierService().list_suppliers(
        db, query=query, trade=trade, region=region,
        is_active=is_active, min_rating=min_rating,
    )
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.get("/export")
async def export_suppliers(db: AsyncSession = Depends(get_db)):
    # Unique per-request path so concurrent downloads don't corrupt each other.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        out = tmp.name
    await SupplierService().export_excel(db, out)
    return FileResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="suppliers.xlsx",
        background=BackgroundTask(lambda: Path(out).unlink(missing_ok=True)),
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    supplier = await SupplierService().get(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int, payload: SupplierUpdate, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    supplier = await SupplierService().update(
        db, supplier_id, **payload.model_dump(exclude_unset=True)
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.post("/{supplier_id}/blacklist", response_model=SupplierResponse)
async def blacklist_supplier(
    supplier_id: int, payload: BlacklistRequest, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    supplier = await SupplierService().blacklist(db, supplier_id, payload.reason)
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.post("/import", response_model=SupplierImportResult)
async def import_suppliers(
    file: UploadFile = File(...),
    update_existing: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> SupplierImportResult:
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                tmp.close()
                Path(tmp_path).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail="Upload exceeds the maximum allowed size",
                )
            tmp.write(chunk)
    try:
        result = await SupplierService().import_excel(
            db, tmp_path, update_existing=update_existing
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return SupplierImportResult(**result)
