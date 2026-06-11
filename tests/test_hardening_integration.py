"""Phase 15: end-to-end middleware-stack integration.

Drives the real ASGI middleware (and, where useful, the real app) to prove that
the pure-ASGI wrappers do NOT corrupt binary downloads, do NOT break the SSE
progress stream, and that a 429 carries the full set of security + correlation
headers through the exact ordering used by app.main.
"""
from __future__ import annotations

import os
import tempfile

import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.middleware import ObservabilityMiddleware, RateLimitMiddleware


@pytest.mark.asyncio
async def test_binary_file_download_not_corrupted_through_middleware():
    # ~2KB of arbitrary binary content, including NULs and a PK (zip) signature.
    payload = (b"\x00\x01\x02PK\x03\x04" + bytes(range(256)) * 8)[:2048]

    fd, path = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)

        app = FastAPI()
        app.add_middleware(ObservabilityMiddleware)

        @app.get("/download")
        async def download():
            return FileResponse(path, media_type="application/octet-stream")

        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as c:
            r = await c.get("/download")

        assert r.status_code == 200
        # Byte-identical: the middleware must not buffer/transcode the body.
        assert r.content == payload
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers.get("x-request-id")
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_sse_progress_through_real_app_stack():
    # Use the real app so the real middleware ordering + the SSE route are
    # exercised. An unknown task id yields the "unknown" event with status 200
    # and needs no DB.
    from app.main import app as real_app

    transport = httpx.ASGITransport(app=real_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/progress/some-unknown-task-id")

    assert r.status_code == 200
    assert r.headers.get("x-request-id")
    assert r.headers["x-content-type-options"] == "nosniff"
    # SSE stream survived the middleware intact.
    assert "event:" in r.text
    assert "progress" in r.text


@pytest.mark.asyncio
async def test_rate_limit_429_carries_headers_end_to_end():
    # Wire the SAME three middleware in the SAME order as app.main.py.
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RateLimitMiddleware, enabled=True, per_minute=1, burst=2
    )
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = None
        for _ in range(12):
            r = await c.get("/ping")
            if r.status_code == 429:
                break

    assert r is not None and r.status_code == 429, (
        "expected a 429 within 12 requests but never observed one"
    )
    assert r.headers.get("x-request-id")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.json()["error"]["type"] == "rate_limited"
