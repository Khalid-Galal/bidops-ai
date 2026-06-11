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

import asyncio
import json
import logging

from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory
from app.models.base import DocumentStatus, ProjectStatus
from app.models.document import Document
from app.models.project import Project
from app.services.indexing.chunking_service import ChunkingService
from app.services.indexing.embedding_service import EmbeddingService
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

# Lazy-initialized indexing services (same pattern as PdfParser's lazy converter).
_chunking_service = None
_embedding_service = None


def _get_chunking_service() -> ChunkingService:
    """Get or create the chunking service singleton."""
    global _chunking_service
    if _chunking_service is None:
        settings = get_settings()
        _chunking_service = ChunkingService(
            max_chunk_chars=settings.chunk_max_chars,
            overlap_chars=settings.chunk_overlap_chars,
        )
    return _chunking_service


def _get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        _embedding_service = EmbeddingService(
            persist_dir=settings.chroma_persist_dir,
            model_name=settings.embedding_model,
        )
    return _embedding_service


async def _get_embedding_service_async() -> EmbeddingService:
    """Construct/return the embedding singleton OFF the event loop.

    The first construction loads the sentence-transformer model (CPU + network
    for HF Hub metadata), which would otherwise block the event loop and make
    the whole server unresponsive during the first ingest (observed ~50s)."""
    svc = await asyncio.to_thread(_get_embedding_service)
    try:
        from app.services.indexing.warmup import mark_models_ready

        mark_models_ready()
    except Exception:  # pragma: no cover - defensive
        pass
    return svc


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

                        # Phase 2: Chunk and index document for search.
                        # Wrapped in try/except so indexing failures do NOT
                        # fail the document parse -- search is secondary.
                        try:
                            chunking_svc = _get_chunking_service()
                            # Model load happens off the event loop (cold start
                            # would otherwise freeze the server ~50s).
                            embedding_svc = await _get_embedding_service_async()

                            # Delete any existing chunks (re-upload case) -- Chroma
                            # I/O, also off the loop.
                            await asyncio.to_thread(
                                embedding_svc.delete_document_chunks,
                                project_id,
                                doc_id,
                            )

                            # Chunk the parsed document.
                            chunks = chunking_svc.chunk_document(
                                document_id=doc_id,
                                pages=parsed.pages,
                                filename=filename,
                            )

                            # Index chunks into ChromaDB.
                            # CPU-bound embedding -- run in thread pool.
                            if chunks:
                                chunk_count = await asyncio.to_thread(
                                    embedding_svc.index_chunks,
                                    project_id,
                                    chunks,
                                )
                                logger.info(
                                    "Indexed %d chunks for %s (doc_id=%d)",
                                    chunk_count,
                                    filename,
                                    doc_id,
                                )

                                # Invalidate the cached BM25 keyword index for
                                # this project so keyword/hybrid search reflects
                                # the newly-indexed chunks (the search service is
                                # a separate singleton with its own cache).
                                try:
                                    from app.api.search import _get_search_service

                                    _get_search_service().invalidate_keyword_index(
                                        project_id
                                    )
                                except Exception as inv_exc:  # pragma: no cover
                                    logger.debug(
                                        "Keyword index invalidation skipped: %s",
                                        inv_exc,
                                    )

                            # Enrich metadata with chunk info.
                            existing_meta = (
                                json.loads(doc.metadata_json)
                                if doc.metadata_json
                                else {}
                            )
                            existing_meta["chunk_count"] = len(chunks)
                            existing_meta["languages_detected"] = list(
                                set(c.language for c in chunks)
                            )
                            doc.metadata_json = json.dumps(
                                existing_meta,
                                ensure_ascii=False,
                                default=str,
                            )
                            await db.commit()

                        except Exception as idx_exc:
                            # Indexing failure should NOT fail document parse.
                            logger.warning(
                                "Indexing failed for %s (doc_id=%d): %s. "
                                "Document parsing succeeded.",
                                filename,
                                doc_id,
                                idx_exc,
                            )

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
