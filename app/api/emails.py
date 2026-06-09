"""Emails API: suggested suppliers, draft-only RFQ creation, email log, and
explicit send. Nothing is auto-sent — send is always a separate POST.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.package import Package
from app.schemas.email import (
    EmailLogResponse,
    EmailSendResult,
    EmailUpdateRequest,
    RFQCreateRequest,
    RFQCreateResult,
    SuggestedSupplierResponse,
)
from app.services.email.rfq_service import RFQService
from app.services.email.smtp_sender import SMTPSender

router = APIRouter(tags=["emails"])


async def _require_package(db: AsyncSession, project_id: int, package_id: int) -> Package:
    package = await db.get(Package, package_id)
    if package is None or package.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    return package


@router.get(
    "/projects/{project_id}/packages/{package_id}/suggested-suppliers",
    response_model=list[SuggestedSupplierResponse],
)
async def suggested_suppliers(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> list[SuggestedSupplierResponse]:
    await _require_package(db, project_id, package_id)
    suppliers = await RFQService().suggested_suppliers(db, package_id)
    return [SuggestedSupplierResponse.model_validate(s) for s in suppliers]


@router.post(
    "/projects/{project_id}/packages/{package_id}/rfq",
    response_model=RFQCreateResult,
    status_code=201,
)
async def create_rfq(
    project_id: int,
    package_id: int,
    payload: RFQCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> RFQCreateResult:
    await _require_package(db, project_id, package_id)
    requested = set(payload.supplier_ids)
    drafts = await RFQService().create_rfq_drafts(
        db, package_id, payload.supplier_ids,
        language=payload.language, custom_message=payload.custom_message,
    )
    created_supplier_ids = {d.supplier_id for d in drafts}
    skipped = [
        f"supplier {sid}: missing or no email address"
        for sid in requested
        if sid not in created_supplier_ids
    ]
    return RFQCreateResult(
        package_id=package_id,
        drafts_created=len(drafts),
        email_ids=[d.id for d in drafts],
        skipped=skipped,
    )


@router.get("/emails", response_model=list[EmailLogResponse])
async def list_emails(
    package_id: int | None = Query(default=None),
    supplier_id: int | None = Query(default=None),
    email_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[EmailLogResponse]:
    emails = await RFQService().list_emails(
        db, package_id=package_id, supplier_id=supplier_id,
        email_type=email_type, status=status,
    )
    return [EmailLogResponse.model_validate(e) for e in emails]


@router.get("/emails/{email_id}", response_model=EmailLogResponse)
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)) -> EmailLogResponse:
    email_log = await RFQService().get_email(db, email_id)
    if email_log is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    return EmailLogResponse.model_validate(email_log)


@router.patch("/emails/{email_id}", response_model=EmailLogResponse)
async def update_email(
    email_id: int, payload: EmailUpdateRequest, db: AsyncSession = Depends(get_db)
) -> EmailLogResponse:
    try:
        email_log = await RFQService().update_draft(
            db, email_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if email_log is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    return EmailLogResponse.model_validate(email_log)


@router.post("/emails/{email_id}/send", response_model=EmailSendResult)
async def send_email(email_id: int, db: AsyncSession = Depends(get_db)) -> EmailSendResult:
    svc = RFQService()
    if await svc.get_email(db, email_id) is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    try:
        email_log = await svc.send(db, email_id, sender=SMTPSender())
    except RuntimeError as exc:  # SMTP not configured
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EmailSendResult(
        email_id=email_log.id,
        status=email_log.status,
        message_id=email_log.message_id,
        error=email_log.error_message,
    )
