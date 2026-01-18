"""Project endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_permission
from app.auth.permissions import Permission
from app.models import Project
from app.models.base import ProjectStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectIngestRequest,
    ProjectIngestResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ProjectListResponse])
async def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[ProjectStatus] = None,
    search: Optional[str] = None,
    archived: bool = False,
) -> PaginatedResponse[ProjectListResponse]:
    """List all projects for the current organization.

    Args:
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page
        status_filter: Filter by status
        search: Search in name/description
        archived: Include archived projects

    Returns:
        Paginated list of projects
    """
    # Base query
    query = select(Project).where(
        Project.organization_id == current_user.organization_id,
        Project.is_archived == archived,
    )

    # Apply filters
    if status_filter:
        query = query.where(Project.status == status_filter)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Project.name.ilike(search_term)) | (Project.code.ilike(search_term))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated results
    query = query.order_by(Project.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    projects = result.scalars().all()

    return PaginatedResponse.create(
        items=[ProjectListResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Create a new project.

    Args:
        request: Project creation data
        db: Database session
        current_user: Authenticated user (must have PROJECT_CREATE permission)

    Returns:
        Created project
    """
    # Check permission
    from app.auth.permissions import check_permission
    if not check_permission(current_user.role, Permission.PROJECT_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Check unique code if provided
    if request.code:
        result = await db.execute(
            select(Project).where(
                Project.code == request.code,
                Project.organization_id == current_user.organization_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project code already exists",
            )

    # Create project
    project = Project(
        name=request.name,
        code=request.code,
        description=request.description,
        folder_path=request.folder_path,
        cloud_link=request.cloud_link,
        config=request.config,
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Get project by ID.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Project details

    Raises:
        HTTPException: If project not found
    """
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

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Update a project.

    Args:
        project_id: Project ID
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated project

    Raises:
        HTTPException: If project not found or permission denied
    """
    # Check permission
    from app.auth.permissions import check_permission
    if not check_permission(current_user.role, Permission.PROJECT_UPDATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Fetch project
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

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """Delete a project (soft delete - archive).

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If project not found or permission denied
    """
    from datetime import datetime, timezone
    from app.auth.permissions import check_permission

    if not check_permission(current_user.role, Permission.PROJECT_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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

    # Soft delete
    project.is_archived = True
    project.archived_at = datetime.now(timezone.utc)
    await db.commit()

    return MessageResponse(message="Project archived successfully")


@router.post("/{project_id}/ingest", response_model=ProjectIngestResponse)
async def start_ingestion(
    project_id: int,
    request: ProjectIngestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectIngestResponse:
    """Start document ingestion for a project.

    This will scan the project folder and process all documents.

    Args:
        project_id: Project ID
        request: Ingestion options
        db: Database session
        current_user: Authenticated user

    Returns:
        Ingestion task info

    Raises:
        HTTPException: If project not found or no folder configured
    """
    from app.auth.permissions import check_permission

    if not check_permission(current_user.role, Permission.DOCUMENT_UPLOAD):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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

    folder_path = request.folder_path or project.folder_path
    if not folder_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No folder path configured for project",
        )

    # Update project status
    project.status = ProjectStatus.INGESTING
    await db.commit()

    # In production, this would queue a background task
    # For now, return placeholder response
    return ProjectIngestResponse(
        message="Ingestion started",
        task_id="task_placeholder",
        total_files=0,  # Would be counted from folder
    )


@router.get("/{project_id}/summary")
async def get_project_summary(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get extracted project summary.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Project summary with evidence

    Raises:
        HTTPException: If project not found
    """
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

    if not project.summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project summary not yet generated",
        )

    return project.summary


@router.get("/{project_id}/checklist")
async def get_project_checklist(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list:
    """Get requirements checklist.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Requirements checklist

    Raises:
        HTTPException: If project not found
    """
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

    return project.checklist or []
