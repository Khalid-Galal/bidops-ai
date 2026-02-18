"""In-memory progress store for tracking document processing tasks.

Provides a simple module-level dictionary to track per-task progress
during document batch processing. Sufficient for single-user v1
deployment. No external dependencies (Redis, etc.) needed.
"""

from __future__ import annotations

# Module-level progress store: task_id -> progress dict
progress_store: dict[str, dict] = {}


def init_progress(task_id: str, total: int) -> None:
    """Initialize progress tracking for a new processing task.

    Args:
        task_id: Unique identifier for this processing batch.
        total: Total number of documents to process.
    """
    progress_store[task_id] = {
        "status": "processing",
        "total": total,
        "processed": 0,
        "current_file": "",
        "errors": [],
        "results": [],
    }


def update_progress(task_id: str, processed: int, current_file: str) -> None:
    """Update the processed count and current file being processed.

    Args:
        task_id: The task to update.
        processed: Number of documents processed so far.
        current_file: Name of the file currently being processed.
    """
    if task_id in progress_store:
        progress_store[task_id]["processed"] = processed
        progress_store[task_id]["current_file"] = current_file


def add_error(task_id: str, filename: str, error: str) -> None:
    """Record an error that occurred during processing of a specific file.

    Args:
        task_id: The task to update.
        filename: Name of the file that failed.
        error: Error message describing what went wrong.
    """
    if task_id in progress_store:
        progress_store[task_id]["errors"].append({
            "filename": filename,
            "error": error,
        })


def add_result(task_id: str, filename: str, status: str, page_count: int | None) -> None:
    """Record the result of processing a specific file.

    Args:
        task_id: The task to update.
        filename: Name of the file that was processed.
        status: Processing result status ("completed" or "failed").
        page_count: Number of pages/sheets extracted, or None on failure.
    """
    if task_id in progress_store:
        progress_store[task_id]["results"].append({
            "filename": filename,
            "status": status,
            "page_count": page_count,
        })


def complete_progress(task_id: str) -> None:
    """Mark a processing task as completed.

    Args:
        task_id: The task to mark complete.
    """
    if task_id in progress_store:
        progress_store[task_id]["status"] = "completed"


def fail_progress(task_id: str, reason: str) -> None:
    """Mark a processing task as failed with a reason.

    Args:
        task_id: The task to mark failed.
        reason: Description of why the task failed.
    """
    if task_id in progress_store:
        progress_store[task_id]["status"] = "failed"
        progress_store[task_id]["error_reason"] = reason


def get_progress(task_id: str) -> dict | None:
    """Get the current progress for a task.

    Args:
        task_id: The task to look up.

    Returns:
        Progress dictionary or None if task_id not found.
    """
    return progress_store.get(task_id)
