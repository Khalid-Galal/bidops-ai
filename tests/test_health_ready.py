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
    # The test DB is reachable, so readiness must be a clean 200/ready/ok.
    assert r.status_code == 200
    body = r.json()
    assert "checks" in body
    assert "database" in body["checks"]
    assert "models_warm" in body["checks"]
    assert body["checks"]["database"] == "ok"
    assert body["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_returns_503_when_db_unreachable(monkeypatch):
    # Simulate a DB outage: entering the session context raises. /ready must
    # degrade to 503 + not_ready + a GENERIC database error (no leaked class).
    class _FailingSession:
        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(
        "app.api.health.async_session_factory", lambda: _FailingSession()
    )

    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "error"
