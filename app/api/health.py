"""Health + readiness endpoints (Phase 15)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session_factory
from app.services.indexing.warmup import models_ready

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness: the process is up and serving."""
    return {"status": "ok", "version": get_settings().app_version}


@router.get("/ready")
async def readiness_check():
    """Readiness: dependencies usable. DB ping is required; model warmth is
    advisory (lazy-loads on first use). Returns 503 if the DB is unreachable."""
    checks: dict[str, object] = {}
    db_ok = True
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised only on DB outage
        db_ok = False
        checks["database"] = f"error: {type(exc).__name__}"
    checks["models_warm"] = models_ready()
    payload = {"status": "ready" if db_ok else "not_ready", "checks": checks}
    return JSONResponse(status_code=200 if db_ok else 503, content=payload)
