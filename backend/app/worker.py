"""Background worker for async tasks using ARQ."""

import asyncio
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings
from app.services.document_service import DocumentService
from app.services.extraction_service import ExtractionService

settings = get_settings()


async def ingest_project_documents(
    ctx: dict,
    project_id: int,
    folder_path: str = None,
    force_reindex: bool = False,
) -> dict:
    """Background task to ingest project documents.

    Args:
        ctx: ARQ context
        project_id: Project ID
        folder_path: Optional folder path override
        force_reindex: Force reprocessing

    Returns:
        Ingestion statistics
    """
    service = DocumentService()

    async def progress_callback(progress: dict):
        """Report progress via Redis pub/sub."""
        redis = ctx.get("redis")
        if redis:
            await redis.publish(
                f"project:{project_id}:ingestion",
                str(progress),
            )

    result = await service.ingest_project_folder(
        project_id=project_id,
        folder_path=folder_path,
        force_reindex=force_reindex,
        callback=progress_callback,
    )

    return result


async def extract_project_summary(
    ctx: dict,
    project_id: int,
    force_refresh: bool = False,
) -> dict:
    """Background task to extract project summary.

    Args:
        ctx: ARQ context
        project_id: Project ID
        force_refresh: Force re-extraction

    Returns:
        Extracted summary
    """
    service = ExtractionService()

    result = await service.extract_project_summary(
        project_id=project_id,
        force_refresh=force_refresh,
    )

    return {"project_id": project_id, "fields_extracted": len(result)}


async def generate_project_checklist(
    ctx: dict,
    project_id: int,
    force_refresh: bool = False,
) -> dict:
    """Background task to generate requirements checklist.

    Args:
        ctx: ARQ context
        project_id: Project ID
        force_refresh: Force re-generation

    Returns:
        Generation result
    """
    service = ExtractionService()

    result = await service.generate_checklist(
        project_id=project_id,
        force_refresh=force_refresh,
    )

    return {"project_id": project_id, "requirements_count": len(result)}


async def classify_all_documents(
    ctx: dict,
    project_id: int,
) -> dict:
    """Background task to classify all project documents.

    Args:
        ctx: ARQ context
        project_id: Project ID

    Returns:
        Classification results
    """
    from sqlalchemy import select
    from app.database import get_db_context
    from app.models import Document
    from app.models.base import DocumentStatus

    service = ExtractionService()
    classified = 0
    failed = 0

    async with get_db_context() as db:
        result = await db.execute(
            select(Document).where(
                Document.project_id == project_id,
                Document.status == DocumentStatus.INDEXED,
            )
        )
        documents = result.scalars().all()

        for doc in documents:
            try:
                await service.classify_document(doc.id)
                classified += 1
            except Exception:
                failed += 1

    return {
        "project_id": project_id,
        "classified": classified,
        "failed": failed,
    }


async def startup(ctx: dict) -> None:
    """Worker startup hook."""
    print("Worker starting up...")
    settings.setup_directories()


async def shutdown(ctx: dict) -> None:
    """Worker shutdown hook."""
    print("Worker shutting down...")


def get_redis_settings() -> RedisSettings:
    """Parse Redis URL into settings."""
    from urllib.parse import urlparse

    parsed = urlparse(settings.REDIS_URL)

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path[1:]) if parsed.path else 0,
        password=parsed.password,
    )


class WorkerSettings:
    """ARQ worker settings."""

    functions = [
        ingest_project_documents,
        extract_project_summary,
        generate_project_checklist,
        classify_all_documents,
    ]

    on_startup = startup
    on_shutdown = shutdown

    redis_settings = get_redis_settings()

    # Worker configuration
    max_jobs = 10
    job_timeout = 3600  # 1 hour max per job
    keep_result = 3600  # Keep results for 1 hour
    poll_delay = 0.5


async def enqueue_task(
    function_name: str,
    **kwargs: Any,
) -> str:
    """Enqueue a background task.

    Args:
        function_name: Name of the function to run
        **kwargs: Arguments to pass to the function

    Returns:
        Job ID
    """
    redis = await create_pool(get_redis_settings())

    job = await redis.enqueue_job(function_name, **kwargs)

    return job.job_id
