"""Packaging API: generate trade packages from BOQ items, list, and inspect."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document
from app.models.package import PackageDocument
from app.models.project import Project
from app.schemas.boq import BOQItemResponse
from app.schemas.packaging import (
    DocumentLinkResult,
    LinkedDocumentResponse,
    PackageDetailResponse,
    PackageExportResult,
    PackageResponse,
    PackagingResult,
)
from app.services.packaging.document_linker import DocumentLinker
from app.services.packaging.package_exporter import PackageExporter
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


@router.post("/link-documents", response_model=DocumentLinkResult)
async def link_documents(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentLinkResult:
    """Link the most relevant documents to each package via semantic search."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    summary = await DocumentLinker().link_all(db, project_id)
    return DocumentLinkResult(**summary)


@router.post("/export", response_model=PackageExportResult)
async def export_packages(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> PackageExportResult:
    """Generate folder structure, BOQ subsets, briefs, and the register on disk."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    summary = await PackageExporter().export_project(db, project_id)
    return PackageExportResult(
        project_id=summary["project_id"],
        packages_exported=summary["packages_exported"],
        register_path=summary["register_path"],
        briefs_pdf=summary["briefs_pdf"],
    )


@router.get("/register")
async def download_register(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Download the master Packages Register.xlsx (run export first)."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    register = Path(PackageExporter()._root) / f"project_{project_id}" / "Packages_Register.xlsx"
    if not register.exists():
        raise HTTPException(
            status_code=404,
            detail="Register not found — run POST /packages/export first.",
        )
    return FileResponse(
        str(register),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"Packages_Register_project_{project_id}.xlsx",
    )


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

    # Build linked documents via an explicit join (never a lazy relationship
    # load) to stay within the async session and avoid MissingGreenlet.
    rows = (
        await db.execute(
            select(PackageDocument, Document.filename)
            .join(Document, Document.id == PackageDocument.document_id)
            .where(PackageDocument.package_id == package_id)
            .order_by(PackageDocument.relevance_score.desc())
        )
    ).all()
    linked_documents = [
        LinkedDocumentResponse(
            document_id=pd.document_id,
            filename=filename,
            relevance_score=pd.relevance_score,
            relevance_reason=pd.relevance_reason,
            excerpt=pd.excerpt,
        )
        for pd, filename in rows
    ]

    return PackageDetailResponse(
        **base.model_dump(),
        items=[BOQItemResponse.model_validate(i) for i in items],
        linked_documents=linked_documents,
    )
