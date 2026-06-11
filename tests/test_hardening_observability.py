"""Phase 15: request-id, security headers, access logging; SSE stays intact."""
from __future__ import annotations

import asyncio
import logging
import re

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


@pytest.mark.asyncio
async def test_malicious_inbound_request_id_is_rejected():
    # A client-supplied id that could inject CRLF (header smuggling) or quotes
    # (JSON-body injection) must NOT be echoed back; a fresh hex id is used.
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        crlf_payload = "evil\r\nSet-Cookie: x=1"
        r1 = await c.get("/ok", headers={"X-Request-ID": crlf_payload})
        r2 = await c.get("/ok", headers={"X-Request-ID": 'a"b'})

    for r in (r1, r2):
        echoed = r.headers["x-request-id"]
        assert "\r" not in echoed
        assert "\n" not in echoed
        assert '"' not in echoed
        # The unsafe value was discarded -> a freshly generated hex id is used.
        assert re.fullmatch(r"[a-f0-9]{32}", echoed)


@pytest.mark.asyncio
async def test_request_id_truncation_boundary():
    # A safe but over-long id is truncated to the 128-char cap.
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/ok", headers={"X-Request-ID": "a" * 200})
    echoed = r.headers["x-request-id"]
    assert len(echoed) == 128
    assert echoed == "a" * 128


@pytest.mark.asyncio
async def test_access_log_emitted(caplog):
    # One structured access line per request, including method, path, and rid=.
    transport = httpx.ASGITransport(app=_app())
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            await c.get("/ok")
    records = [r for r in caplog.records if r.name == "app.access"]
    assert records, "expected an app.access log record"
    msg = records[-1].getMessage()
    assert "GET" in msg
    assert "/ok" in msg
    assert "rid=" in msg
