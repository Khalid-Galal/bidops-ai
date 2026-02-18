"""Document processing orchestrator.

Routes uploaded files to the appropriate parser, stores results in the
database, and updates the in-memory progress store for SSE streaming.

Critical design decisions:
- Documents are processed SEQUENTIALLY (not concurrently) to avoid
  SQLite "database is locked" errors.
- Each document update gets its OWN database session (session lifecycle
  must not span the full background task).
- The background task is fire-and-forget via asyncio.create_task().
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.models.base import DocumentStatus, ProjectStatus
from app.models.document import Document
from app.models.project import Project
from app.services.parsing.base import get_parser_for_file
from app.services.progress import (
    add_error,
    add_result,
    complete_progress,
    fail_progress,
    init_progress,
    update_progress,
)

logger = logging.getLogger(__name__)


async def process_documents_batch(
    task_id: str,
    project_id: int,
    file_records: list[dict],
) -> None:
    """Process a batch of uploaded documents sequentially.

    This function runs as a background task (asyncio.create_task). It
    processes each document one at a time, updating the progress store
    and database after each file.

    Args:
        task_id: Unique identifier for progress tracking via SSE.
        project_id: Database ID of the project these documents belong to.
        file_records: List of dicts with keys:
            - doc_id (int): Document record ID in the database.
            - filename (str): Original filename for display/logging.
            - file_path (str): Absolute path to the saved file on disk.
            - file_type (str): File extension (e.g. ".pdf").
    """
    init_progress(task_id, len(file_records))

    try:
        for i, record in enumerate(file_records):
            filename = record["filename"]
            file_path = record["file_path"]
            doc_id = record["doc_id"]

            update_progress(task_id, i, filename)

            try:
                # Get the appropriate parser for this file type.
                parser = get_parser_for_file(filename)

                # Parse the document (may be CPU-intensive, uses to_thread internally).
                parsed = await parser.parse(file_path)

                # Check if parser returned warnings indicating a parse failure.
                # Parsers return empty ParsedDocument with warnings on error
                # rather than raising exceptions.
                has_parse_error = (
                    not parsed.full_text
                    and parsed.warnings
                    and any("error" in w.lower() for w in parsed.warnings)
                )

                # Update database with results -- new session per document.
                async with async_session_factory() as db:
                    doc = await db.get(Document, doc_id)
                    if doc is None:
                        logger.warning(
                            "Document %d not found in database, skipping", doc_id
                        )
                        add_error(task_id, filename, "Document record not found")
                        continue

                    if has_parse_error:
                        doc.status = DocumentStatus.FAILED.value
                        doc.error_message = "; ".join(parsed.warnings)
                        doc.processing_time_ms = parsed.processing_time_ms

                        # Update project failure count.
                        project = await db.get(Project, project_id)
                        if project:
                            project.failed_documents = (
                                project.failed_documents or 0
                            ) + 1

                        await db.commit()
                        add_error(task_id, filename, doc.error_message)
                        add_result(task_id, filename, "failed", None)
                    else:
                        doc.status = DocumentStatus.COMPLETED.value
                        doc.extracted_text = parsed.full_text
                        doc.tables_json = json.dumps(
                            parsed.tables, ensure_ascii=False, default=str
                        )
                        doc.metadata_json = json.dumps(
                            parsed.metadata, ensure_ascii=False, default=str
                        )
                        doc.page_count = parsed.page_count
                        doc.processing_time_ms = parsed.processing_time_ms

                        # Update project success count.
                        project = await db.get(Project, project_id)
                        if project:
                            project.processed_documents = (
                                project.processed_documents or 0
                            ) + 1

                        await db.commit()
                        add_result(task_id, filename, "completed", parsed.page_count)

                logger.info(
                    "Processed %s (%d/%d): %s, %d pages in %dms",
                    filename,
                    i + 1,
                    len(file_records),
                    "completed" if not has_parse_error else "failed",
                    parsed.page_count,
                    parsed.processing_time_ms,
                )

            except Exception as exc:
                logger.exception("Error processing %s: %s", filename, exc)

                # Update database to mark document as failed.
                try:
                    async with async_session_factory() as db:
                        doc = await db.get(Document, doc_id)
                        if doc:
                            doc.status = DocumentStatus.FAILED.value
                            doc.error_message = str(exc)

                            project = await db.get(Project, project_id)
                            if project:
                                project.failed_documents = (
                                    project.failed_documents or 0
                                ) + 1

                            await db.commit()
                except Exception as db_exc:
                    logger.exception(
                        "Failed to update DB for %s: %s", filename, db_exc
                    )

                add_error(task_id, filename, str(exc))
                add_result(task_id, filename, "failed", None)

        # Update final progress count.
        update_progress(task_id, len(file_records), "")

        # Determine final project status.
        async with async_session_factory() as db:
            project = await db.get(Project, project_id)
            if project:
                if project.failed_documents >= project.total_documents:
                    project.status = ProjectStatus.FAILED.value
                else:
                    project.status = ProjectStatus.READY.value
                await db.commit()

        complete_progress(task_id)
        logger.info(
            "Batch processing complete for task %s: %d documents",
            task_id,
            len(file_records),
        )

    except Exception as exc:
        logger.exception("Batch processing failed for task %s: %s", task_id, exc)
        fail_progress(task_id, str(exc))

        # Try to mark project as failed.
        try:
            async with async_session_factory() as db:
                project = await db.get(Project, project_id)
                if project:
                    project.status = ProjectStatus.FAILED.value
                    await db.commit()
        except Exception:
            logger.exception("Failed to update project status for %d", project_id)
