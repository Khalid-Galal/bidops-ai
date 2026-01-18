"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.common import HealthResponse

router = APIRouter()
settings = get_settings()


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Check system health.

    Returns status of all services.
    """
    response = HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        database="unknown",
        redis="unknown",
        qdrant="unknown",
    )

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        response.database = "connected"
    except Exception:
        response.database = "disconnected"
        response.status = "degraded"

    # Check Redis (if configured)
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        response.redis = "connected"
        await r.close()
    except Exception:
        response.redis = "disconnected"

    # Check Qdrant (if configured)
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.QDRANT_URL)
        client.get_collections()
        response.qdrant = "connected"
    except Exception:
        response.qdrant = "disconnected"

    return response


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Kubernetes readiness probe."""
    try:
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}


@router.get("/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe."""
    return {"alive": True}
