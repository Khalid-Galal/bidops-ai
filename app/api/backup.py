"""Manual backup trigger + status for the HF Dataset snapshot persistence."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.services.backup.backup_service import get_backup_service

router = APIRouter(tags=["backup"])

# The endpoint is unauthenticated (like the rest of the app), so guard the
# expensive tar+upload behind a cooldown and an in-progress check: spamming
# POST /backup must not queue unbounded snapshot work on a public Space.
_MANUAL_COOLDOWN_SECONDS = 30.0


@router.post("/backup")
async def backup_now():
    """Snapshot the data dir to the configured HF Dataset repo right now."""
    svc = get_backup_service()
    if not svc.enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Backup not configured. Set BIDOPS_BACKUP_DATASET_REPO and a "
                "write token (HF_TOKEN or BIDOPS_HF_TOKEN)."
            ),
        )
    if svc.backup_in_progress():
        raise HTTPException(status_code=429, detail="A backup is already running.")
    if svc.last_backup_at and (time.time() - svc.last_backup_at) < _MANUAL_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=429,
            detail=f"Backup ran recently; retry in {int(_MANUAL_COOLDOWN_SECONDS)}s.",
        )
    result = await svc.backup()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=f"Backup failed: {result.get('error')}")
    return result


@router.get("/backup/status")
async def backup_status():
    """Whether snapshots are configured, the target repo, and last result."""
    svc = get_backup_service()
    return {
        "enabled": svc.enabled(),
        "repo": svc.repo_id or None,
        "last_backup_at": (
            datetime.fromtimestamp(svc.last_backup_at, tz=timezone.utc).isoformat()
            if svc.last_backup_at
            else None
        ),
        "last_error": svc.last_error,
    }
