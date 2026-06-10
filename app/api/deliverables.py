"""Deliverables API: assemble and download the client-ready submission bundle."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.services.deliverables.deliverables_service import DeliverablesService

router = APIRouter(tags=["deliverables"])


@router.post("/projects/{project_id}/deliverables/build")
async def build_deliverables(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await DeliverablesService().build(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/deliverables/download")
async def download_deliverables(project_id: int):
    folder = DeliverablesService().project_dir(project_id)
    if not folder.is_dir() or not any(folder.iterdir()):
        raise HTTPException(
            status_code=404,
            detail="Deliverables not built — run POST .../deliverables/build first.",
        )
    # Unique temp base per request so concurrent downloads cannot collide.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="")
    base = tmp.name
    tmp.close()
    Path(base).unlink(missing_ok=True)
    zip_path = shutil.make_archive(base, "zip", root_dir=str(folder))
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"deliverables_project_{project_id}.zip",
        background=BackgroundTask(lambda: Path(zip_path).unlink(missing_ok=True)),
    )
