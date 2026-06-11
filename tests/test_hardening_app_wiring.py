"""Phase 15: the real app has the hardening wired (headers, request-id, /ready,
error envelope) and existing routes/pages still work."""
from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_real_app_has_security_headers_and_request_id():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_real_app_ready_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/ready")
    assert r.status_code in (200, 503)
    assert "database" in r.json()["checks"]


@pytest.mark.asyncio
async def test_real_app_404_envelope_unchanged_for_httpexception():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/projects/99999999")
    assert r.status_code == 404
    assert "detail" in r.json()  # HTTPException shape preserved
