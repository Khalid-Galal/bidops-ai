"""HTML page routes for the web interface.

Serves Jinja2-rendered pages for project management and document upload.
These routes are separate from the JSON API routes -- they return HTML
responses for the browser.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import templates
from app.models.document import Document
from app.models.project import Project
from app.services.dashboard.dashboard_service import DashboardService

router = APIRouter(tags=["pages"])


@router.get("/")
async def index_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Render the home page with the list of all projects.

    Args:
        request: FastAPI Request object (required by Jinja2).
        db: Database session (injected by FastAPI).

    Returns:
        TemplateResponse rendering index.html with projects data.
    """
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return templates.TemplateResponse(
        request, "index.html", {"projects": projects}
    )


@router.get("/projects/{project_id}")
async def project_page(
    request: Request,
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Render the project detail page with upload area and document list.

    Args:
        request: FastAPI Request object (required by Jinja2).
        project_id: ID of the project to display.
        db: Database session (injected by FastAPI).

    Returns:
        TemplateResponse rendering project.html with project and documents.

    Raises:
        HTTPException: 404 if project not found.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found",
        )

    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at)
    )
    documents = result.scalars().all()

    return templates.TemplateResponse(
        request, "project.html", {"project": project, "documents": documents}
    )


@router.get("/projects/{project_id}/dashboard")
async def dashboard_page(
    request: Request,
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Render the project status dashboard page."""
    try:
        data = await DashboardService().project_dashboard(db, project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        ) from exc
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"d": data},
    )


@router.get("/suppliers")
async def suppliers_page(request: Request):
    """Render the global supplier database page (data loads via the JSON API)."""
    return templates.TemplateResponse(request, "suppliers.html", {})


@router.get("/projects/{project_id}/workbench")
async def workbench_page(
    request: Request,
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Render the tabbed v2 workbench for one project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return templates.TemplateResponse(request, "workbench.html", {"project": project})
