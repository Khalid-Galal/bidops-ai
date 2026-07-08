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
    # Hermetic: seed an in-memory DB with the schema and override get_db so the
    # query succeeds and the missing project yields a real 404 -- independent of
    # any ambient data/bidops.db state. Without a valid schema the query would
    # raise OperationalError (500) and never exercise the HTTPException path.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.database import get_db
    from app.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get("/api/projects/99999999")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
    assert r.status_code == 404
    assert "detail" in r.json()  # HTTPException shape preserved
