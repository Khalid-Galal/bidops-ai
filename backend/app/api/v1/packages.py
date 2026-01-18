"""Package and BOQ endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.auth.permissions import Permission, check_permission
from app.models import BOQItem, Package, PackageDocument, Project
from app.models.base import PackageStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.package import (
    BOQClassifyRequest,
    BOQExportRequest,
    BOQItemResponse,
    BOQItemUpdate,
    BOQParseRequest,
    BOQParseResponse,
    BOQStatisticsResponse,
    PackageBriefRequest,
    PackageBriefResponse,
    PackageCreate,
    PackageDocumentResponse,
    PackageFolderRequest,
    PackageFolderResponse,
    PackageGenerateRequest,
    PackageGenerateResponse,
    PackageLinkDocumentsRequest,
    PackageLinkDocumentsResponse,
    PackageListResponse,
    PackageResponse,
    PackageStatisticsResponse,
    PackageUpdate,
)
from app.services.boq_service import BOQService
from app.services.packaging_service import PackagingService

router = APIRouter()


# ============================================================================
# BOQ Endpoints
# ============================================================================


@router.post(
    "/projects/{project_id}/boq/parse",
    response_model=BOQParseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def parse_boq(
    project_id: int,
    request: BOQParseRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> BOQParseResponse:
    """Parse BOQ from an Excel file.

    Args:
        project_id: Project ID
        request: BOQ parsing options
        db: Database session
        current_user: Authenticated user

    Returns:
        Parsing results and statistics
    """
    if not check_permission(current_user.role, Permission.PROJECT_UPDATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
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

    service = BOQService()

    try:
        result = await service.parse_boq_excel(
            file_path=request.file_path,
            project_id=project_id,
            sheet_name=request.sheet_name,
            header_row=request.header_row,
            column_mapping=request.column_mapping,
        )
        return BOQParseResponse(**result)
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


@router.get(
    "/projects/{project_id}/boq",
    response_model=PaginatedResponse[BOQItemResponse],
)
async def list_boq_items(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    trade_category: Optional[str] = None,
    section: Optional[str] = None,
    assigned: Optional[bool] = None,
    search: Optional[str] = None,
) -> PaginatedResponse[BOQItemResponse]:
    """List BOQ items for a project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page
        trade_category: Filter by trade category
        section: Filter by section
        assigned: Filter by package assignment
        search: Search in description

    Returns:
        Paginated list of BOQ items
    """
    # Verify project access
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

    # Build query
    query = select(BOQItem).where(BOQItem.project_id == project_id)

    if trade_category:
        query = query.where(BOQItem.trade_category == trade_category)

    if section:
        query = query.where(BOQItem.section == section)

    if assigned is not None:
        if assigned:
            query = query.where(BOQItem.package_id != None)
        else:
            query = query.where(BOQItem.package_id == None)

    if search:
        query = query.where(BOQItem.description.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated
    query = query.order_by(BOQItem.section, BOQItem.line_number)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse.create(
        items=[BOQItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/projects/{project_id}/boq/statistics",
    response_model=BOQStatisticsResponse,
)
async def get_boq_statistics(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> BOQStatisticsResponse:
    """Get BOQ statistics for a project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        BOQ statistics
    """
    # Verify project access
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

    # Total items
    total = await db.execute(
        select(func.count(BOQItem.id)).where(BOQItem.project_id == project_id)
    )
    total_count = total.scalar() or 0

    # By trade category
    by_trade_result = await db.execute(
        select(BOQItem.trade_category, func.count(BOQItem.id))
        .where(BOQItem.project_id == project_id)
        .group_by(BOQItem.trade_category)
    )
    trade_counts = {row[0] or "UNCLASSIFIED": row[1] for row in by_trade_result}

    # By section
    by_section_result = await db.execute(
        select(BOQItem.section, func.count(BOQItem.id))
        .where(BOQItem.project_id == project_id)
        .group_by(BOQItem.section)
    )
    section_counts = {row[0] or "NO SECTION": row[1] for row in by_section_result}

    return BOQStatisticsResponse(
        total_items=total_count,
        by_trade=trade_counts,
        by_section=section_counts,
    )


@router.patch(
    "/boq/{item_id}",
    response_model=BOQItemResponse,
)
async def update_boq_item(
    item_id: int,
    request: BOQItemUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> BOQItemResponse:
    """Update a BOQ item.

    Args:
        item_id: BOQ item ID
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated BOQ item
    """
    if not check_permission(current_user.role, Permission.PROJECT_UPDATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Get item with project check
    result = await db.execute(
        select(BOQItem)
        .join(Project)
        .where(
            BOQItem.id == item_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOQ item not found",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    return BOQItemResponse.model_validate(item)


@router.post(
    "/projects/{project_id}/boq/classify",
    response_model=dict,
)
async def classify_boq_items(
    project_id: int,
    request: BOQClassifyRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Classify BOQ items using AI.

    Args:
        project_id: Project ID
        request: Classification options
        db: Database session
        current_user: Authenticated user

    Returns:
        Classification results
    """
    if not check_permission(current_user.role, Permission.PROJECT_UPDATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
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

    service = BOQService()
    result = await service.classify_items_with_ai(
        project_id=project_id,
        batch_size=request.batch_size,
    )

    return result


@router.post(
    "/projects/{project_id}/boq/export",
    response_class=FileResponse,
)
async def export_boq(
    project_id: int,
    request: BOQExportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Export BOQ to Excel file.

    Args:
        project_id: Project ID
        request: Export options
        db: Database session
        current_user: Authenticated user

    Returns:
        Excel file download
    """
    import tempfile
    from pathlib import Path

    # Verify project access
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

    service = BOQService()

    # Determine output path
    output_path = request.output_path
    if not output_path:
        temp_dir = tempfile.mkdtemp()
        output_path = str(Path(temp_dir) / f"{project.code or project_id}_BOQ.xlsx")

    try:
        file_path = await service.export_boq_excel(
            project_id=project_id,
            output_path=output_path,
            include_pricing=request.include_pricing,
        )
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=Path(file_path).name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# Package Endpoints
# ============================================================================


@router.get(
    "/projects/{project_id}/packages",
    response_model=PaginatedResponse[PackageListResponse],
)
async def list_packages(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[PackageStatus] = None,
    trade_category: Optional[str] = None,
) -> PaginatedResponse[PackageListResponse]:
    """List packages for a project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page
        status_filter: Filter by status
        trade_category: Filter by trade category

    Returns:
        Paginated list of packages
    """
    # Verify project access
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

    # Build query
    query = select(Package).where(Package.project_id == project_id)

    if status_filter:
        query = query.where(Package.status == status_filter)

    if trade_category:
        query = query.where(Package.trade_category == trade_category)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated
    query = query.order_by(Package.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    packages = result.scalars().all()

    return PaginatedResponse.create(
        items=[PackageListResponse.model_validate(p) for p in packages],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/projects/{project_id}/packages",
    response_model=PackageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_package(
    project_id: int,
    request: PackageCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageResponse:
    """Create a new package.

    Args:
        project_id: Project ID
        request: Package creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created package
    """
    if not check_permission(current_user.role, Permission.PACKAGE_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
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

    # Generate code if not provided
    code = request.code
    if not code:
        count = await db.execute(
            select(func.count(Package.id)).where(Package.project_id == project_id)
        )
        seq = (count.scalar() or 0) + 1
        trade_abbr = request.trade_category[:3].upper()
        code = f"PKG-{project.code or project_id}-{trade_abbr}-{seq:03d}"

    # Create package
    package = Package(
        project_id=project_id,
        name=request.name,
        code=code,
        trade_category=request.trade_category,
        description=request.description,
        status=PackageStatus.DRAFT,
        submission_deadline=request.submission_deadline,
        submission_instructions=request.submission_instructions,
        estimated_value=request.estimated_value,
        currency=request.currency,
    )
    db.add(package)
    await db.commit()
    await db.refresh(package)

    return PackageResponse.model_validate(package)


@router.get(
    "/packages/{package_id}",
    response_model=PackageResponse,
)
async def get_package(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageResponse:
    """Get package by ID.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Package details
    """
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

    return PackageResponse.model_validate(package)


@router.patch(
    "/packages/{package_id}",
    response_model=PackageResponse,
)
async def update_package(
    package_id: int,
    request: PackageUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageResponse:
    """Update a package.

    Args:
        package_id: Package ID
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated package
    """
    if not check_permission(current_user.role, Permission.PACKAGE_UPDATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(package, field, value)

    await db.commit()
    await db.refresh(package)

    return PackageResponse.model_validate(package)


@router.delete(
    "/packages/{package_id}",
    response_model=MessageResponse,
)
async def delete_package(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """Delete a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message
    """
    if not check_permission(current_user.role, Permission.PACKAGE_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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

    # Unassign BOQ items
    await db.execute(
        BOQItem.__table__.update()
        .where(BOQItem.package_id == package_id)
        .values(package_id=None)
    )

    await db.delete(package)
    await db.commit()

    return MessageResponse(message="Package deleted successfully")


@router.post(
    "/projects/{project_id}/packages/generate",
    response_model=PackageGenerateResponse,
)
async def generate_packages(
    project_id: int,
    request: PackageGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageGenerateResponse:
    """Auto-generate packages from BOQ items.

    Args:
        project_id: Project ID
        request: Generation options
        db: Database session
        current_user: Authenticated user

    Returns:
        Generation results
    """
    if not check_permission(current_user.role, Permission.PACKAGE_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
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

    service = PackagingService()

    result = await service.generate_packages_from_boq(
        project_id=project_id,
        grouping=request.grouping,
        min_items=request.min_items,
        max_items=request.max_items,
    )

    return PackageGenerateResponse(**result)


@router.post(
    "/packages/{package_id}/link-documents",
    response_model=PackageLinkDocumentsResponse,
)
async def link_documents_to_package(
    package_id: int,
    request: PackageLinkDocumentsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageLinkDocumentsResponse:
    """Link documents to a package.

    Args:
        package_id: Package ID
        request: Linking options
        db: Database session
        current_user: Authenticated user

    Returns:
        Linking results
    """
    if not check_permission(current_user.role, Permission.PACKAGE_UPDATE):
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

    service = PackagingService()

    result = await service.link_documents_to_package(
        package_id=package_id,
        auto_link=request.auto_link,
        document_ids=request.document_ids,
    )

    return PackageLinkDocumentsResponse(**result)


@router.get(
    "/packages/{package_id}/documents",
    response_model=list[PackageDocumentResponse],
)
async def get_package_documents(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[PackageDocumentResponse]:
    """Get documents linked to a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        List of linked documents
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

    result = await db.execute(
        select(PackageDocument).where(PackageDocument.package_id == package_id)
    )
    links = result.scalars().all()

    return [PackageDocumentResponse.model_validate(link) for link in links]


@router.get(
    "/packages/{package_id}/items",
    response_model=list[BOQItemResponse],
)
async def get_package_items(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[BOQItemResponse]:
    """Get BOQ items in a package.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        List of BOQ items
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

    result = await db.execute(
        select(BOQItem)
        .where(BOQItem.package_id == package_id)
        .order_by(BOQItem.line_number)
    )
    items = result.scalars().all()

    return [BOQItemResponse.model_validate(item) for item in items]


@router.post(
    "/packages/{package_id}/create-folder",
    response_model=PackageFolderResponse,
)
async def create_package_folder(
    package_id: int,
    request: PackageFolderRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageFolderResponse:
    """Create folder structure for a package.

    Args:
        package_id: Package ID
        request: Folder options
        db: Database session
        current_user: Authenticated user

    Returns:
        Folder creation results
    """
    if not check_permission(current_user.role, Permission.PACKAGE_UPDATE):
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

    service = PackagingService()

    result = await service.create_package_folder(
        package_id=package_id,
        base_path=request.base_path,
    )

    return PackageFolderResponse(**result)


@router.post(
    "/packages/{package_id}/generate-brief",
    response_model=PackageBriefResponse,
)
async def generate_package_brief(
    package_id: int,
    request: PackageBriefRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageBriefResponse:
    """Generate PDF brief for a package.

    Args:
        package_id: Package ID
        request: Brief options
        db: Database session
        current_user: Authenticated user

    Returns:
        Brief generation results
    """
    if not check_permission(current_user.role, Permission.PACKAGE_UPDATE):
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

    service = PackagingService()

    brief_path = await service.generate_package_brief(
        package_id=package_id,
        output_path=request.output_path,
    )

    return PackageBriefResponse(
        package_id=package_id,
        brief_path=brief_path,
    )


@router.get(
    "/packages/{package_id}/brief",
    response_class=FileResponse,
)
async def download_package_brief(
    package_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Download package brief PDF.

    Args:
        package_id: Package ID
        db: Database session
        current_user: Authenticated user

    Returns:
        PDF file download
    """
    import os

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

    if not package.brief_path or not os.path.exists(package.brief_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package brief not generated",
        )

    return FileResponse(
        package.brief_path,
        media_type="application/pdf",
        filename=f"{package.code}_Brief.pdf",
    )


@router.post(
    "/packages/{package_id}/assign-items",
    response_model=MessageResponse,
)
async def assign_items_to_package(
    package_id: int,
    item_ids: list[int],
    db: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """Assign BOQ items to a package.

    Args:
        package_id: Package ID
        item_ids: List of BOQ item IDs to assign
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message
    """
    if not check_permission(current_user.role, Permission.PACKAGE_UPDATE):
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
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    # Update items
    await db.execute(
        BOQItem.__table__.update()
        .where(
            BOQItem.id.in_(item_ids),
            BOQItem.project_id == package.project_id,
        )
        .values(package_id=package_id)
    )

    # Update package item count
    count_result = await db.execute(
        select(func.count(BOQItem.id)).where(BOQItem.package_id == package_id)
    )
    package.total_items = count_result.scalar() or 0

    await db.commit()

    return MessageResponse(
        message=f"Assigned {len(item_ids)} items to package",
        data={"items_assigned": len(item_ids)},
    )


@router.get(
    "/projects/{project_id}/packages/statistics",
    response_model=PackageStatisticsResponse,
)
async def get_package_statistics(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PackageStatisticsResponse:
    """Get package statistics for a project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Package statistics
    """
    # Verify project access
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

    service = PackagingService()
    stats = await service.get_package_statistics(project_id)

    return PackageStatisticsResponse(**stats)
