"""Dashboard API: aggregated project status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.dashboard import ProjectDashboard
from app.services.dashboard.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/dashboard", response_model=ProjectDashboard)
async def project_dashboard(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> ProjectDashboard:
    try:
        data = await DashboardService().project_dashboard(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectDashboard(**data)
