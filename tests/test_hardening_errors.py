"""Phase 15: unhandled exceptions render a JSON envelope, no stack-trace leak;
HTTPException/validation shapes are unchanged."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.errors import register_exception_handlers
from app.middleware import ObservabilityMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    @app.get("/notfound")
    async def notfound():
        raise HTTPException(status_code=404, detail="thing not found")

    return app


@pytest.mark.asyncio
async def test_unhandled_exception_returns_envelope_without_leaking():
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["type"] == "internal_error"
    assert body["error"]["message"] == "Internal server error"
    assert "secret internal detail" not in r.text  # no stack-trace / detail leak
    assert body["error"]["request_id"]              # correlation id present
    assert r.headers["x-content-type-options"] == "nosniff"  # security headers on errors
    assert r.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_httpexception_shape_is_unchanged():
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/notfound")
    assert r.status_code == 404
    assert r.json() == {"detail": "thing not found"}  # FastAPI default preserved
