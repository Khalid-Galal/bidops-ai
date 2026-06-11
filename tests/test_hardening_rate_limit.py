"""Phase 15: rate limiter is off by default, returns 429 with envelope when tripped."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.middleware import ObservabilityMiddleware, RateLimitMiddleware


def _app(*, enabled: bool, per_minute: int = 60, burst: int = 2) -> FastAPI:
    app = FastAPI()
    # Order: Observability outermost (assigns request id), then RateLimit.
    app.add_middleware(
        RateLimitMiddleware, enabled=enabled, per_minute=per_minute, burst=burst
    )
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_disabled_limiter_never_blocks():
    transport = httpx.ASGITransport(app=_app(enabled=False))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        for _ in range(20):
            assert (await c.get("/ping")).status_code == 200


@pytest.mark.asyncio
async def test_enabled_limiter_trips_after_burst():
    transport = httpx.ASGITransport(app=_app(enabled=True, per_minute=1, burst=2))
    codes = []
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        for _ in range(5):
            codes.append((await c.get("/ping")).status_code)
    assert codes[0] == 200 and codes[1] == 200      # burst allowed
    assert 429 in codes                              # subsequent blocked
    # 429 carries the envelope + correlation id + security headers (set by
    # Observability, which wraps RateLimit). Keep requesting until a 429 lands,
    # then assert unconditionally.
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = None
        for _ in range(12):
            r = await c.get("/ping")
            if r.status_code == 429:
                break
        assert r is not None and r.status_code == 429, (
            "expected a 429 within 12 requests but never observed one"
        )
        assert r.json()["error"]["type"] == "rate_limited"
        assert r.headers.get("x-request-id")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "SAMEORIGIN"
