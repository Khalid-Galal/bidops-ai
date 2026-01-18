"""Supplier and Email endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.auth.permissions import Permission, check_permission
from app.models import Supplier
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.supplier import (
    ClarificationEmailRequest,
    EmailBulkSendRequest,
    EmailBulkSendResponse,
    EmailCreateRequest,
    EmailLogResponse,
    SupplierBlacklistRequest,
    SupplierCreate,
    SupplierImportRequest,
    SupplierImportResponse,
    SupplierListResponse,
    SupplierPerformanceResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier_service import SupplierService
from app.services.email_service import EmailService

router = APIRouter()


# ============================================================================
# Supplier Endpoints
# ============================================================================


@router.get("/suppliers", response_model=PaginatedResponse[SupplierListResponse])
async def list_suppliers(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    query: Optional[str] = None,
    trade_category: Optional[str] = None,
    region: Optional[str] = None,
    is_active: Optional[bool] = True,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
) -> PaginatedResponse[SupplierListResponse]:
    """List suppliers with filters.

    Args:
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page
        query: Search query
        trade_category: Filter by trade
        region: Filter by region
        is_active: Filter by active status
        min_rating: Minimum rating filter

    Returns:
        Paginated list of suppliers
    """
    service = SupplierService()

    trade_categories = [trade_category] if trade_category else None

    suppliers, total = await service.search_suppliers(
        organization_id=current_user.organization_id,
        query=query,
        trade_categories=trade_categories,
        region=region,
        is_active=is_active,
        min_rating=min_rating,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse.create(
        items=[SupplierListResponse.model_validate(s) for s in suppliers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    request: SupplierCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Create a new supplier.

    Args:
        request: Supplier creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created supplier
    """
    if not check_permission(current_user.role, Permission.SUPPLIER_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = SupplierService()

    supplier = await service.create_supplier(
        organization_id=current_user.organization_id,
        name=request.name,
        emails=request.emails,
        trade_categories=request.trade_categories,
        name_ar=request.name_ar,
        code=request.code,
        phone=request.phone,
        fax=request.fax,
        address=request.address,
        website=request.website,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        region=request.region,
        country=request.country,
        preferred_language=request.preferred_language,
        notes=request.notes,
    )

    return SupplierResponse.model_validate(supplier)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Get supplier by ID.

    Args:
        supplier_id: Supplier ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Supplier details
    """
    service = SupplierService()

    supplier = await service.get_supplier(
        supplier_id=supplier_id,
        organization_id=current_user.organization_id,
    )

    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    return SupplierResponse.model_validate(supplier)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    request: SupplierUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Update a supplier.

    Args:
        supplier_id: Supplier ID
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated supplier
    """
    if not check_permission(current_user.role, Permission.SUPPLIER_UPDATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.organization_id == current_user.organization_id,
        )
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(supplier, field, value)

    await db.commit()
    await db.refresh(supplier)

    return SupplierResponse.model_validate(supplier)


@router.delete("/suppliers/{supplier_id}", response_model=MessageResponse)
async def delete_supplier(
    supplier_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """Delete a supplier (soft delete - deactivate).

    Args:
        supplier_id: Supplier ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message
    """
    if not check_permission(current_user.role, Permission.SUPPLIER_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.organization_id == current_user.organization_id,
        )
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    supplier.is_active = False
    await db.commit()

    return MessageResponse(message="Supplier deactivated successfully")


@router.post("/suppliers/import", response_model=SupplierImportResponse)
async def import_suppliers(
    request: SupplierImportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierImportResponse:
    """Import suppliers from Excel file.

    Args:
        request: Import options
        db: Database session
        current_user: Authenticated user

    Returns:
        Import results
    """
    if not check_permission(current_user.role, Permission.SUPPLIER_IMPORT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = SupplierService()

    try:
        result = await service.import_from_excel(
            file_path=request.file_path,
            organization_id=current_user.organization_id,
            update_existing=request.update_existing,
        )
        return SupplierImportResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/suppliers/export", response_class=FileResponse)
async def export_suppliers(
    db: DbSession,
    current_user: CurrentUser,
    trade_category: Optional[str] = None,
) -> FileResponse:
    """Export suppliers to Excel file.

    Args:
        db: Database session
        current_user: Authenticated user
        trade_category: Filter by trade

    Returns:
        Excel file download
    """
    import tempfile
    from pathlib import Path

    service = SupplierService()

    trade_categories = [trade_category] if trade_category else None
    temp_dir = tempfile.mkdtemp()
    output_path = str(Path(temp_dir) / "suppliers_export.xlsx")

    file_path = await service.export_to_excel(
        organization_id=current_user.organization_id,
        output_path=output_path,
        trade_categories=trade_categories,
    )

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="suppliers_export.xlsx",
    )


@router.post(
    "/suppliers/{supplier_id}/blacklist",
    response_model=SupplierResponse,
)
async def blacklist_supplier(
    supplier_id: int,
    request: SupplierBlacklistRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Blacklist a supplier.

    Args:
        supplier_id: Supplier ID
        request: Blacklist reason
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated supplier
    """
    if not check_permission(current_user.role, Permission.SUPPLIER_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = SupplierService()

    try:
        supplier = await service.blacklist_supplier(
            supplier_id=supplier_id,
            organization_id=current_user.organization_id,
            reason=request.reason,
        )
        return SupplierResponse.model_validate(supplier)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/suppliers/{supplier_id}/performance",
    response_model=SupplierPerformanceResponse,
)
async def get_supplier_performance(
    supplier_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierPerformanceResponse:
    """Get supplier performance statistics.

    Args:
        supplier_id: Supplier ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Performance statistics
    """
    service = SupplierService()

    # Verify access
    supplier = await service.get_supplier(
        supplier_id=supplier_id,
        organization_id=current_user.organization_id,
    )

    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    stats = await service.update_performance_stats(supplier_id)
    return SupplierPerformanceResponse(**stats)


@router.get(
    "/suppliers/for-trade/{trade_category}",
    response_model=list[SupplierListResponse],
)
async def get_suppliers_for_trade(
    trade_category: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
) -> list[SupplierListResponse]:
    """Get active suppliers for a specific trade.

    Args:
        trade_category: Trade category
        db: Database session
        current_user: Authenticated user
        limit: Maximum suppliers to return

    Returns:
        List of suppliers
    """
    service = SupplierService()

    suppliers = await service.get_suppliers_for_trade(
        organization_id=current_user.organization_id,
        trade_category=trade_category.upper(),
        limit=limit,
    )

    return [SupplierListResponse.model_validate(s) for s in suppliers]


# ============================================================================
# Email Endpoints
# ============================================================================


@router.post(
    "/packages/{package_id}/emails/rfq",
    response_model=EmailLogResponse,
)
async def create_rfq_email(
    package_id: int,
    request: EmailCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailLogResponse:
    """Create an RFQ email for a supplier.

    Args:
        package_id: Package ID
        request: Email creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created email log
    """
    if not check_permission(current_user.role, Permission.EMAIL_SEND):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = EmailService()

    try:
        email = await service.create_rfq_email(
            package_id=package_id,
            supplier_id=request.supplier_id,
            attachments=request.attachments,
            custom_message=request.custom_message,
        )
        return EmailLogResponse.model_validate(email)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/packages/{package_id}/emails/send-bulk",
    response_model=EmailBulkSendResponse,
)
async def send_bulk_rfq(
    package_id: int,
    request: EmailBulkSendRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailBulkSendResponse:
    """Send RFQ emails to multiple suppliers.

    Args:
        package_id: Package ID
        request: Bulk send data
        db: Database session
        current_user: Authenticated user

    Returns:
        Bulk send results
    """
    if not check_permission(current_user.role, Permission.EMAIL_SEND):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = EmailService()

    result = await service.send_bulk_rfq(
        package_id=package_id,
        supplier_ids=request.supplier_ids,
        attachments=request.attachments,
    )

    return EmailBulkSendResponse(**result)


@router.post("/emails/{email_id}/send", response_model=dict)
async def send_email(
    email_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Send an email.

    Args:
        email_id: Email log ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Send result
    """
    if not check_permission(current_user.role, Permission.EMAIL_SEND):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = EmailService()

    try:
        result = await service.send_email(email_id)
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to send email"),
            )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/offers/{offer_id}/clarification-email",
    response_model=EmailLogResponse,
)
async def create_clarification_email(
    offer_id: int,
    request: ClarificationEmailRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailLogResponse:
    """Create a clarification request email.

    Args:
        offer_id: Offer ID
        request: Clarification data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created email log
    """
    if not check_permission(current_user.role, Permission.EMAIL_SEND):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    service = EmailService()

    try:
        email = await service.create_clarification_email(
            offer_id=offer_id,
            clarification_items=request.clarification_items,
            response_days=request.response_days,
        )
        return EmailLogResponse.model_validate(email)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/packages/{package_id}/emails",
    response_model=PaginatedResponse[EmailLogResponse],
)
async def get_package_emails(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[EmailLogResponse]:
    """Get emails for a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of emails
    """
    service = EmailService()

    emails, total = await service.get_email_history(
        package_id=package_id,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse.create(
        items=[EmailLogResponse.model_validate(e) for e in emails],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/suppliers/{supplier_id}/emails",
    response_model=PaginatedResponse[EmailLogResponse],
)
async def get_supplier_emails(
    supplier_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[EmailLogResponse]:
    """Get emails for a supplier.

    Args:
        supplier_id: Supplier ID
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of emails
    """
    service = EmailService()

    emails, total = await service.get_email_history(
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse.create(
        items=[EmailLogResponse.model_validate(e) for e in emails],
        total=total,
        page=page,
        page_size=page_size,
    )
