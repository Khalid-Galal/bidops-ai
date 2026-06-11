"""Phase 15: request-id, security headers, access logging; SSE stays intact."""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.middleware import SECURITY_HEADERS, ObservabilityMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/ok")
    async def ok():
        return {"hello": "world"}

    @app.get("/stream")
    async def stream():
        async def gen():
            for i in range(3):
                yield f"chunk{i}\n"
                await asyncio.sleep(0)
        return StreamingResponse(gen(), media_type="text/plain")

    return app


@pytest.mark.asyncio
async def test_security_headers_and_request_id_present():
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/ok")
    assert r.status_code == 200
    for k in (b"x-content-type-options", b"x-frame-options", b"referrer-policy"):
        assert k.decode() in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"
    # a request id is generated when the client does not supply one
    assert r.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_inbound_request_id_is_echoed():
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/ok", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


@pytest.mark.asyncio
async def test_streaming_response_not_broken_by_middleware():
    # Pure-ASGI middleware must not buffer/break a streaming body.
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/stream")
    assert r.status_code == 200
    assert r.text == "chunk0\nchunk1\nchunk2\n"
    assert r.headers["x-content-type-options"] == "nosniff"
