"""Packaging API: generate trade packages from BOQ items, list, and inspect."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.boq import BOQItemResponse
from app.schemas.packaging import (
    PackageDetailResponse,
    PackageResponse,
    PackagingResult,
)
from app.services.packaging.packaging_service import PackagingService

router = APIRouter(prefix="/projects/{project_id}/packages", tags=["packaging"])


@router.post("/generate", response_model=PackagingResult)
async def generate_packages(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> PackagingResult:
    """(Re)generate trade packages from the project's classified BOQ items."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    summary = await PackagingService().generate(db, project_id)
    return PackagingResult(**summary)


@router.get("", response_model=list[PackageResponse])
async def list_packages(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[PackageResponse]:
    packages = await PackagingService().list_packages(db, project_id)
    return [PackageResponse.model_validate(p) for p in packages]


@router.get("/{package_id}", response_model=PackageDetailResponse)
async def package_detail(
    project_id: int,
    package_id: int,
    db: AsyncSession = Depends(get_db),
) -> PackageDetailResponse:
    svc = PackagingService()
    package = await svc.get_package(db, package_id)
    if package is None or package.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    items = await svc.get_package_items(db, package_id)
    base = PackageResponse.model_validate(package)
    return PackageDetailResponse(
        **base.model_dump(),
        items=[BOQItemResponse.model_validate(i) for i in items],
    )
