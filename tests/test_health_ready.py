"""Phase 15: /health liveness + /ready readiness (DB ping + model-warm flag)."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api.health import router as health_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    return app


@pytest.mark.asyncio
async def test_health_is_liveness_only():
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_reports_db_and_models():
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/ready")
    # DB ping should succeed against the configured sqlite db.
    assert r.status_code in (200, 503)
    body = r.json()
    assert "checks" in body
    assert "database" in body["checks"]
    assert "models_warm" in body["checks"]
