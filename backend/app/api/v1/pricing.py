"""Pricing and export endpoints."""

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.auth.permissions import Permission, check_permission
from app.models import BOQItem, Package, Project
from app.schemas.common import MessageResponse
from app.schemas.pricing import (
    ApplyMarkupRequest,
    ApplyMarkupResponse,
    BulkPriceUpdateRequest,
    BulkPriceUpdateResponse,
    CopyPricesRequest,
    CopyPricesResponse,
    CostBreakdownResponse,
    DashboardResponse,
    ExportBOQRequest,
    ExportBOQResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    PackageTotalsResponse,
    PriceComparisonResponse,
    PricePopulateRequest,
    PricePopulateResponse,
    ProjectTotalsResponse,
    UpdateItemPriceRequest,
)
from app.services.pricing_service import PricingService
from app.services.export_service import ExportService

router = APIRouter()


# ============================================================================
# Pricing Endpoints
# ============================================================================


@router.post(
    "/packages/{package_id}/pricing/populate",
    response_model=PricePopulateResponse,
)
async def populate_prices_from_offer(
    package_id: int,
    request: PricePopulateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PricePopulateResponse:
    """Populate BOQ prices from a selected offer.

    Args:
        package_id: Package ID
        request: Population options
        db: Database session
        current_user: Authenticated user

    Returns:
        Population results
    """
    if not check_permission(current_user.role, Permission.PRICING_POPULATE):
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

    service = PricingService()

    try:
        result = await service.populate_from_offer(
            offer_id=request.offer_id,
            apply_markup=request.apply_markup,
            markup_percentage=request.markup_percentage,
        )
        return PricePopulateResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/packages/{package_id}/pricing/totals",
    response_model=PackageTotalsResponse,
)
async def get_package_totals(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageTotalsResponse:
    """Get pricing totals for a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Package pricing totals
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

    service = PricingService()
    totals = await service.calculate_package_totals(package_id)

    return PackageTotalsResponse(**totals)


@router.get(
    "/projects/{project_id}/pricing/totals",
    response_model=ProjectTotalsResponse,
)
async def get_project_totals(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectTotalsResponse:
    """Get pricing totals for entire project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Project pricing totals
    """
    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = PricingService()

    try:
        totals = await service.calculate_project_totals(project_id)
        return ProjectTotalsResponse(**totals)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/packages/{package_id}/pricing/markup",
    response_model=ApplyMarkupResponse,
)
async def apply_markup(
    package_id: int,
    request: ApplyMarkupRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApplyMarkupResponse:
    """Apply markup to package items.

    Args:
        package_id: Package ID
        request: Markup options
        db: Database session
        current_user: Authenticated user

    Returns:
        Markup application results
    """
    if not check_permission(current_user.role, Permission.PRICING_POPULATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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

    service = PricingService()

    result = await service.apply_markup_to_package(
        package_id=package_id,
        markup_percentage=request.markup_percentage,
        only_unpriced=request.only_unpriced,
    )

    return ApplyMarkupResponse(**result)


@router.get(
    "/packages/{package_id}/pricing/comparison",
    response_model=PriceComparisonResponse,
)
async def get_price_comparison(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PriceComparisonResponse:
    """Get price comparison across all offers.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Price comparison data
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

    service = PricingService()

    try:
        comparison = await service.get_price_comparison(package_id)
        return PriceComparisonResponse(**comparison)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/pricing/breakdown",
    response_model=CostBreakdownResponse,
)
async def get_cost_breakdown(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CostBreakdownResponse:
    """Get detailed cost breakdown by trade.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Cost breakdown data
    """
    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = PricingService()
    breakdown = await service.get_cost_breakdown(project_id)

    return CostBreakdownResponse(**breakdown)


@router.patch(
    "/boq/{item_id}/price",
    response_model=dict,
)
async def update_item_price(
    item_id: int,
    request: UpdateItemPriceRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Update a single BOQ item price.

    Args:
        item_id: BOQ item ID
        request: New price data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated item data
    """
    if not check_permission(current_user.role, Permission.PRICING_POPULATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(BOQItem)
        .join(Project)
        .where(
            BOQItem.id == item_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOQ item not found",
        )

    service = PricingService()

    try:
        item = await service.update_item_price(
            item_id=item_id,
            unit_rate=request.unit_rate,
            source=request.source,
        )
        return {
            "id": item.id,
            "unit_rate": item.unit_rate,
            "total_price": item.total_price,
            "price_source": item.price_source,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/projects/{project_id}/pricing/bulk-update",
    response_model=BulkPriceUpdateResponse,
)
async def bulk_update_prices(
    project_id: int,
    request: BulkPriceUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> BulkPriceUpdateResponse:
    """Bulk update BOQ item prices.

    Args:
        project_id: Project ID
        request: Bulk update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Update results
    """
    if not check_permission(current_user.role, Permission.PRICING_POPULATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = PricingService()

    updates = [u.model_dump() for u in request.updates]
    result = await service.bulk_update_prices(updates)

    return BulkPriceUpdateResponse(**result)


@router.post(
    "/packages/{package_id}/pricing/copy",
    response_model=CopyPricesResponse,
)
async def copy_prices(
    package_id: int,
    request: CopyPricesRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> CopyPricesResponse:
    """Copy prices from another package.

    Args:
        package_id: Target package ID
        request: Copy options
        db: Database session
        current_user: Authenticated user

    Returns:
        Copy results
    """
    if not check_permission(current_user.role, Permission.PRICING_POPULATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify target package access
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
            detail="Target package not found",
        )

    # Verify source package access
    result = await db.execute(
        select(Package)
        .join(Project)
        .where(
            Package.id == request.source_package_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source package not found",
        )

    service = PricingService()

    result = await service.copy_prices_between_packages(
        source_package_id=request.source_package_id,
        target_package_id=package_id,
        match_by=request.match_by,
    )

    return CopyPricesResponse(**result)


# ============================================================================
# Export Endpoints
# ============================================================================


@router.post(
    "/projects/{project_id}/export/boq",
    response_class=FileResponse,
)
async def export_priced_boq(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
    include_breakdown: bool = True,
    format_style: str = "standard",
) -> FileResponse:
    """Export priced BOQ to Excel.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user
        include_breakdown: Include trade breakdown sheet
        format_style: Format style

    Returns:
        Excel file download
    """
    if not check_permission(current_user.role, Permission.PRICING_EXPORT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = ExportService()

    temp_dir = tempfile.mkdtemp()
    output_path = str(Path(temp_dir) / f"{project.code or project_id}_BOQ.xlsx")

    try:
        file_path = await service.export_priced_boq(
            project_id=project_id,
            output_path=output_path,
            include_breakdown=include_breakdown,
            format_style=format_style,
        )

        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"{project.code or project_id}_Priced_BOQ.xlsx",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/projects/{project_id}/export/pricing-report",
    response_class=FileResponse,
)
async def export_pricing_report(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Generate and export pricing summary report as PDF.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        PDF file download
    """
    if not check_permission(current_user.role, Permission.PRICING_EXPORT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = ExportService()

    temp_dir = tempfile.mkdtemp()
    output_path = str(Path(temp_dir) / f"{project.code or project_id}_Pricing_Report.pdf")

    try:
        file_path = await service.generate_pricing_report_pdf(
            project_id=project_id,
            output_path=output_path,
        )

        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=f"{project.code or project_id}_Pricing_Report.pdf",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/packages/{package_id}/export/evaluation",
    response_class=FileResponse,
)
async def export_offer_evaluation(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Export offer evaluation report to Excel.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Excel file download
    """
    if not check_permission(current_user.role, Permission.PRICING_EXPORT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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

    service = ExportService()

    temp_dir = tempfile.mkdtemp()
    output_path = str(Path(temp_dir) / f"{package.code}_Evaluation.xlsx")

    try:
        file_path = await service.export_offer_evaluation_report(
            package_id=package_id,
            output_path=output_path,
        )

        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"{package.code}_Evaluation_Report.xlsx",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/projects/{project_id}/export/status-report",
    response_class=FileResponse,
)
async def export_status_report(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Generate project status report as PDF.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        PDF file download
    """
    if not check_permission(current_user.role, Permission.PRICING_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = ExportService()

    temp_dir = tempfile.mkdtemp()
    output_path = str(Path(temp_dir) / f"{project.code or project_id}_Status_Report.pdf")

    try:
        file_path = await service.generate_project_status_report(
            project_id=project_id,
            output_path=output_path,
        )

        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=f"{project.code or project_id}_Status_Report.pdf",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# Dashboard Endpoint
# ============================================================================


@router.get(
    "/projects/{project_id}/dashboard",
    response_model=DashboardResponse,
)
async def get_dashboard(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> DashboardResponse:
    """Get dashboard statistics for a project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Dashboard statistics
    """
    # Verify access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    service = ExportService()

    try:
        stats = await service.get_dashboard_statistics(project_id)
        return DashboardResponse(**stats)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
