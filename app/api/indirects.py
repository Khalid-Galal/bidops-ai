"""Indirects API: the project indirect-cost breakdown and the full project
cost rollup (direct -> indirects -> markups -> VAT -> grand total)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.indirects import IndirectsResult, ProjectCostSummary
from app.services.indirects.indirects_service import IndirectsService

router = APIRouter(tags=["indirects"])


@router.get("/projects/{project_id}/indirects", response_model=IndirectsResult)
async def get_indirects(
    project_id: int,
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> IndirectsResult:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await IndirectsService().indirects_result(
        db, project_id, duration_months=duration_months, location=location
    )
    return IndirectsResult(**result)


@router.get("/projects/{project_id}/cost-summary", response_model=ProjectCostSummary)
async def get_cost_summary(
    project_id: int,
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> ProjectCostSummary:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await IndirectsService().project_cost_summary(
        db, project_id, duration_months=duration_months, location=location
    )
    return ProjectCostSummary(**result)
