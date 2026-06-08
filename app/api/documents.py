"""Document upload, listing, and SSE progress streaming endpoints.

Upload endpoint saves files to disk and starts background parsing.
Progress endpoint streams real-time updates via Server-Sent Events.
Documents endpoint lists all documents for a project.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.database import get_db
from app.models.base import DocumentStatus, ProjectStatus
from app.models.document import Document
from app.models.project import Project
from app.schemas.document import DocumentResponse, UploadResponse
from app.services.document_service import process_documents_batch
from app.services.progress import get_progress

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls",
    ".txt", ".md", ".csv",
    ".eml", ".msg",
    ".pptx",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp",
    ".zip",
}


@router.post(
    "/projects/{project_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    project_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more documents to a project for processing.

    Files are saved to disk and Document records created in the database.
    A background task is started to parse all uploaded files sequentially.
    Returns a task_id for tracking progress via SSE.

    Args:
        project_id: ID of the project to upload documents to.
        files: List of uploaded files (PDF, DOCX, XLSX supported).
        db: Database session (injected by FastAPI).

    Returns:
        UploadResponse with task_id, uploaded count, skipped count, and filenames.

    Raises:
        HTTPException: 404 if project not found, 400 if no valid files.
    """
    # Verify project exists.
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found",
        )

    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded_names: list[str] = []
    skipped_count = 0
    file_records: list[dict] = []

    for file in files:
        if not file.filename:
            skipped_count += 1
            continue

        # Check file extension.
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            logger.info("Skipping unsupported file: %s (ext=%s)", file.filename, ext)
            skipped_count += 1
            continue

        # Generate safe filename to avoid collisions and path traversal.
        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        dest_path = upload_dir / safe_name

        # Stream file to disk (NOT await file.read() which loads into memory).
        with open(dest_path, "wb") as dest_file:
            shutil.copyfileobj(file.file, dest_file)

        file_size = dest_path.stat().st_size

        # Create Document record in database.
        doc = Document(
            project_id=project_id,
            filename=file.filename,
            file_path=str(dest_path.as_posix()),
            file_type=ext,
            file_size=file_size,
            status=DocumentStatus.PENDING.value,
        )
        db.add(doc)
        await db.flush()  # Get the doc.id assigned.

        file_records.append({
            "doc_id": doc.id,
            "filename": file.filename,
            "file_path": str(dest_path),
            "file_type": ext,
        })
        uploaded_names.append(file.filename)

    if not file_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported files uploaded. Allowed: PDF, DOCX, XLSX.",
        )

    # Update project counters and status.
    project.total_documents = (project.total_documents or 0) + len(file_records)
    project.status = ProjectStatus.INGESTING.value

    await db.commit()

    # Generate task ID and start background processing.
    task_id = str(uuid.uuid4())

    asyncio.create_task(
        process_documents_batch(task_id, project_id, file_records)
    )

    logger.info(
        "Upload complete for project %d: %d files, task_id=%s",
        project_id,
        len(file_records),
        task_id,
    )

    return UploadResponse(
        task_id=task_id,
        uploaded=len(file_records),
        skipped=skipped_count,
        filenames=uploaded_names,
    )


@router.get(
    "/projects/{project_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_documents(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all documents belonging to a project.

    Args:
        project_id: ID of the project.
        db: Database session (injected by FastAPI).

    Returns:
        List of DocumentResponse objects ordered by creation date.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists.
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
    return documents


@router.get("/progress/{task_id}")
async def stream_progress(task_id: str):
    """Stream real-time processing progress via Server-Sent Events.

    Polls the in-memory progress store every 0.5 seconds and yields
    JSON-serialized progress data. The stream ends when the task reaches
    "completed", "failed", or "unknown" status.

    Args:
        task_id: The task ID returned from the upload endpoint.

    Returns:
        EventSourceResponse streaming progress events.
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from the progress store."""
        while True:
            progress = get_progress(task_id)

            if progress is None:
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "status": "unknown",
                        "total": 0,
                        "processed": 0,
                        "current_file": "",
                        "errors": [],
                    }),
                }
                break

            yield {
                "event": "progress",
                "data": json.dumps({
                    "status": progress["status"],
                    "total": progress["total"],
                    "processed": progress["processed"],
                    "current_file": progress["current_file"],
                    "errors": progress["errors"],
                    "results": progress.get("results", []),
                }),
            }

            if progress["status"] in ("completed", "failed"):
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
