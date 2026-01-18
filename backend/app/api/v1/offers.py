"""Offer evaluation endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.auth.permissions import Permission, check_permission
from app.models import Package, Project
from app.models.supplier import SupplierOffer
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.supplier import (
    OfferComparisonResponse,
    OfferComplianceResponse,
    OfferCreate,
    OfferEvaluateRequest,
    OfferEvaluateResponse,
    OfferExtractResponse,
    OfferListResponse,
    OfferRankResponse,
    OfferResponse,
    OfferSelectRequest,
    OfferUpdate,
)
from app.services.offer_service import OfferService

router = APIRouter()


@router.post(
    "/packages/{package_id}/offers",
    response_model=OfferResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_offer(
    package_id: int,
    request: OfferCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferResponse:
    """Upload a new supplier offer.

    Args:
        package_id: Package ID
        request: Offer creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created offer
    """
    if not check_permission(current_user.role, Permission.OFFER_UPLOAD):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify package access
    result = await db.execute(
        select(Package)
        .join(Project)
        .where(
            Package.id == package_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    service = OfferService()

    try:
        offer = await service.create_offer(
            package_id=package_id,
            supplier_id=request.supplier_id,
            file_paths=request.file_paths,
        )

        # Get supplier name for response
        result = await db.execute(
            select(SupplierOffer)
            .options(selectinload(SupplierOffer.supplier))
            .where(SupplierOffer.id == offer.id)
        )
        offer = result.scalar_one()

        response = OfferResponse.model_validate(offer)
        response.supplier_name = offer.supplier.name
        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/packages/{package_id}/offers",
    response_model=PaginatedResponse[OfferListResponse],
)
async def list_offers(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
) -> PaginatedResponse[OfferListResponse]:
    """List offers for a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page
        status_filter: Filter by status

    Returns:
        Paginated list of offers
    """
    # Verify package access
    result = await db.execute(
        select(Package)
        .join(Project)
        .where(
            Package.id == package_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    from sqlalchemy import func
    from app.models.base import OfferStatus

    query = (
        select(SupplierOffer)
        .options(selectinload(SupplierOffer.supplier))
        .where(SupplierOffer.package_id == package_id)
    )

    if status_filter:
        try:
            status_enum = OfferStatus(status_filter)
            query = query.where(SupplierOffer.status == status_enum)
        except ValueError:
            pass

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch
    query = query.order_by(SupplierOffer.overall_score.desc().nullslast())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    offers = list(result.scalars().all())

    items = []
    for offer in offers:
        item = OfferListResponse.model_validate(offer)
        item.supplier_name = offer.supplier.name
        items.append(item)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/offers/{offer_id}", response_model=OfferResponse)
async def get_offer(
    offer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferResponse:
    """Get offer by ID.

    Args:
        offer_id: Offer ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Offer details
    """
    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.supplier),
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    # Verify access
    if offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    response = OfferResponse.model_validate(offer)
    response.supplier_name = offer.supplier.name
    return response


@router.patch("/offers/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: int,
    request: OfferUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferResponse:
    """Update an offer.

    Args:
        offer_id: Offer ID
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated offer
    """
    if not check_permission(current_user.role, Permission.OFFER_EVALUATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.supplier),
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    if offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(offer, field, value)

    await db.commit()
    await db.refresh(offer)

    response = OfferResponse.model_validate(offer)
    response.supplier_name = offer.supplier.name
    return response


@router.delete("/offers/{offer_id}", response_model=MessageResponse)
async def delete_offer(
    offer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """Delete an offer.

    Args:
        offer_id: Offer ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message
    """
    if not check_permission(current_user.role, Permission.OFFER_EVALUATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    if offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    await db.delete(offer)
    await db.commit()

    return MessageResponse(message="Offer deleted successfully")


@router.post("/offers/{offer_id}/extract", response_model=OfferExtractResponse)
async def extract_offer_data(
    offer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferExtractResponse:
    """Extract commercial data from offer using AI.

    Args:
        offer_id: Offer ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Extracted data
    """
    if not check_permission(current_user.role, Permission.OFFER_EVALUATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer or offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    service = OfferService()

    try:
        extracted = await service.extract_offer_data(offer_id)
        return OfferExtractResponse(**extracted)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


@router.post("/offers/{offer_id}/compliance", response_model=OfferComplianceResponse)
async def check_offer_compliance(
    offer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferComplianceResponse:
    """Check offer compliance against requirements.

    Args:
        offer_id: Offer ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Compliance analysis
    """
    if not check_permission(current_user.role, Permission.OFFER_EVALUATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer or offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    service = OfferService()

    try:
        compliance = await service.check_compliance(offer_id)
        return OfferComplianceResponse(**compliance)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {str(e)}",
        )


@router.post("/offers/{offer_id}/evaluate", response_model=OfferEvaluateResponse)
async def evaluate_offer(
    offer_id: int,
    request: OfferEvaluateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferEvaluateResponse:
    """Evaluate and score an offer.

    Args:
        offer_id: Offer ID
        request: Evaluation parameters
        db: Database session
        current_user: Authenticated user

    Returns:
        Evaluation results
    """
    if not check_permission(current_user.role, Permission.OFFER_EVALUATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer or offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    service = OfferService()

    result = await service.evaluate_offer(
        offer_id=offer_id,
        technical_score=request.technical_score,
        commercial_weight=request.commercial_weight,
        technical_weight=request.technical_weight,
    )

    return OfferEvaluateResponse(**result)


@router.get(
    "/packages/{package_id}/offers/rank",
    response_model=list[OfferRankResponse],
)
async def rank_offers(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[OfferRankResponse]:
    """Rank all offers for a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Ranked list of offers
    """
    # Verify access
    result = await db.execute(
        select(Package)
        .join(Project)
        .where(
            Package.id == package_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    service = OfferService()
    ranked = await service.rank_offers(package_id)

    return [OfferRankResponse(**r) for r in ranked]


@router.get(
    "/packages/{package_id}/offers/compare",
    response_model=OfferComparisonResponse,
)
async def compare_offers(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferComparisonResponse:
    """Get offer comparison summary.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Comparison data
    """
    # Verify access
    result = await db.execute(
        select(Package)
        .join(Project)
        .where(
            Package.id == package_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    service = OfferService()

    try:
        comparison = await service.compare_offers(package_id)
        return OfferComparisonResponse(**comparison)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/packages/{package_id}/offers/export",
    response_class=FileResponse,
)
async def export_offer_comparison(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Export offer comparison to Excel.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Excel file download
    """
    import tempfile
    from pathlib import Path

    # Verify access
    result = await db.execute(
        select(Package)
        .join(Project)
        .where(
            Package.id == package_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    service = OfferService()

    temp_dir = tempfile.mkdtemp()
    output_path = str(Path(temp_dir) / f"{package.code}_comparison.xlsx")

    file_path = await service.export_comparison_excel(
        package_id=package_id,
        output_path=output_path,
    )

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{package.code}_comparison.xlsx",
    )


@router.post("/offers/{offer_id}/select", response_model=OfferResponse)
async def select_offer(
    offer_id: int,
    request: OfferSelectRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> OfferResponse:
    """Select an offer as the winner.

    Args:
        offer_id: Offer ID
        request: Selection notes
        db: Database session
        current_user: Authenticated user

    Returns:
        Selected offer
    """
    if not check_permission(current_user.role, Permission.OFFER_SELECT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer or offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    service = OfferService()

    try:
        selected = await service.select_offer(
            offer_id=offer_id,
            notes=request.notes,
        )

        # Refresh for response
        result = await db.execute(
            select(SupplierOffer)
            .options(selectinload(SupplierOffer.supplier))
            .where(SupplierOffer.id == selected.id)
        )
        offer = result.scalar_one()

        response = OfferResponse.model_validate(offer)
        response.supplier_name = offer.supplier.name
        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/offers/{offer_id}/details", response_model=dict)
async def get_offer_details(
    offer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get detailed offer information.

    Args:
        offer_id: Offer ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Detailed offer data
    """
    # Verify access
    result = await db.execute(
        select(SupplierOffer)
        .options(
            selectinload(SupplierOffer.package).selectinload(Package.project),
        )
        .where(SupplierOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()

    if not offer or offer.package.project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found",
        )

    service = OfferService()

    try:
        return await service.get_offer_details(offer_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
