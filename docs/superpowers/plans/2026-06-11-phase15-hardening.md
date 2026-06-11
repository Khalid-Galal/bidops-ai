# Phase 15 — Hardening / NFRs (no auth) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add production-grade operational hardening to the BidOps AI FastAPI app — request correlation + structured access logging, security headers, a consistent JSON error envelope (no stack-trace leaks), a readiness probe, configurable rate limiting, and a fix for the cold-start event-loop freeze the E2E shakedown surfaced — WITHOUT adding authentication/RBAC (deferred by user decision; personal single-user use).

**Architecture:** All cross-cutting concerns are **pure-ASGI middleware** (NOT `BaseHTTPMiddleware`) so they never buffer or break the SSE progress stream or file-download `StreamingResponse`s. A single `ObservabilityMiddleware` assigns/propagates a request id (stored in `scope["state"]` so handlers and exception handlers can read `request.state.request_id`), injects security + correlation headers by intercepting the `http.response.start` ASGI message, and emits one structured access-log line per request. A separate `RateLimitMiddleware` implements a per-client token bucket. A global `Exception` handler renders a JSON envelope for unhandled 500s (the only error shape that is currently inconsistent) while leaving FastAPI's `HTTPException`/validation error shapes UNCHANGED so the existing 306 tests keep passing. The cold-start freeze is fixed by moving embedding-model construction + Chroma delete/index OFF the event loop in the ingest background task, plus an opt-in startup model warmup gated on `/ready`.

**Tech Stack:** FastAPI / Starlette ASGI, async SQLAlchemy 2.0 (`text("SELECT 1")` for readiness ping), pytest-asyncio + httpx `ASGITransport`, `asgi-lifespan` only if needed (avoid — tests target the app directly). No new third-party dependencies.

---

## Design constraints (read before coding)

1. **Do NOT change the shape of existing `HTTPException` / `RequestValidationError` responses.** Many of the 306 tests assert `response.json()["detail"] == "..."`. Only add a handler for **unhandled `Exception`** (status 500), which currently returns Starlette's opaque `"Internal Server Error"` plaintext — wrapping that in a JSON envelope is pure improvement and breaks nothing.
2. **Middleware must be pure-ASGI.** `BaseHTTPMiddleware` consumes the response body iterator and can break `EventSourceResponse` (the `/progress/{task_id}` SSE endpoint) and large file downloads. Implement by wrapping `send` and only touching the `http.response.start` message.
3. **Middleware execution order (outer → inner):** `Observability` → `RateLimit` → `CORS` → app. Achieve by ADDING them in reverse (CORS already added first; then RateLimit; then Observability last = outermost). The request id must be assigned by `Observability` before `RateLimit` runs, so a 429 response can carry it and be logged.
4. **`request.state.request_id`:** Starlette backs `request.state` with `scope.setdefault("state", {})`. Set `scope["state"]["request_id"]` inside `Observability` on the way in; the same scope object reaches route handlers AND the exception handler (built by the outer `ServerErrorMiddleware` from the same scope), so both can read it.
5. **Error response headers:** The global `Exception` handler's `JSONResponse` is produced by `ServerErrorMiddleware`, which sits OUTSIDE our `Observability` middleware — so our middleware will NOT inject headers onto it. Therefore the handler must set `X-Request-ID` + the security headers on its own `JSONResponse`. Share the `SECURITY_HEADERS` constant between middleware and handler.
6. **Tests must not trigger model loads.** `warmup_models_on_startup` defaults to `False`; the test client targets the app without running lifespan, so warmup never fires in the suite.

---

## File Structure

- **Create** `app/middleware.py` — `SECURITY_HEADERS` constant, `ObservabilityMiddleware` (request-id + access log + security headers), `RateLimitMiddleware` (token bucket). Pure ASGI.
- **Create** `app/errors.py` — `register_exception_handlers(app)` registering an unhandled-`Exception` → 500 JSON-envelope handler. Reuses `SECURITY_HEADERS`.
- **Create** `app/services/indexing/warmup.py` — `warmup_models()` (sync; constructs the embedding + chunking singletons so the model loads once) and a `models_ready()` flag accessor.
- **Modify** `app/config.py` — add `app_version`, rate-limit + warmup settings.
- **Modify** `app/api/health.py` — add `GET /ready` (DB ping + model-warm flag); keep `GET /health` as liveness, sourced from `app_version`.
- **Modify** `app/services/document_service.py` — offload embedding-service construction + `delete_document_chunks` + `index_chunks` off the event loop; mark models ready when constructed.
- **Modify** `app/main.py` — wire middleware (correct order), register exception handlers, optional startup warmup, single version source.
- **Create tests** `tests/test_hardening_observability.py`, `tests/test_hardening_errors.py`, `tests/test_hardening_rate_limit.py`, `tests/test_health_ready.py`, `tests/test_hardening_warmup.py`.

Tests build an app instance and drive it with `httpx.AsyncClient(transport=ASGITransport(app=...))` (the Phase-14 page-smoke pattern). Where a test needs a fresh app with specific settings, it constructs middleware/handlers onto a throwaway `FastAPI()` or calls `get_settings.cache_clear()` after setting env.

---

### Task 1: Settings additions

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_hardening_warmup.py` (settings assertions live with warmup tests)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardening_warmup.py
"""Phase 15: settings + model warmup."""
from __future__ import annotations

from app.config import Settings


def test_hardening_settings_have_safe_defaults():
    s = Settings()
    # New NFR knobs exist with conservative defaults.
    assert s.app_version  # non-empty version string
    assert s.rate_limit_enabled is False          # off by default -> zero UX risk
    assert s.rate_limit_per_minute == 120          # lenient default when enabled
    assert s.rate_limit_burst == 30
    assert s.warmup_models_on_startup is False      # tests/pure-pricing users unaffected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_warmup.py::test_hardening_settings_have_safe_defaults -v`
Expected: FAIL with `AttributeError` (no `app_version`).

- [ ] **Step 3: Add settings**

In `app/config.py`, inside `class Settings`, after `app_title`:

```python
    app_version: str = "0.1.0"

    # NFR / hardening (Phase 15). Rate limiting is OFF by default (single-user
    # local app); when enabled it is a per-client-IP token bucket.
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 30
    # Load the embedding/NLI models in a background thread at startup so the
    # first ingest/search is not slow. Off by default so the test suite and
    # pure-pricing workflows never pay the cost.
    warmup_models_on_startup: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_warmup.py::test_hardening_settings_have_safe_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_hardening_warmup.py
git commit -m "feat(phase-15): add NFR settings (version, rate-limit, warmup) with safe defaults"
```

---

### Task 2: Observability middleware (request-id + access log + security headers)

**Files:**
- Create: `app/middleware.py`
- Test: `tests/test_hardening_observability.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardening_observability.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_observability.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.middleware'`.

- [ ] **Step 3: Create `app/middleware.py`**

```python
"""Pure-ASGI cross-cutting middleware (Phase 15 hardening).

Implemented as raw ASGI (NOT starlette.middleware.base.BaseHTTPMiddleware) so
they never consume/buffer the response body iterator -- which would break the
SSE progress stream (/progress/{task_id}) and large file downloads. They only
read the request scope and rewrite the `http.response.start` message headers.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.access")

# Conservative security headers. Header names/values are bytes (ASGI raw form).
# No strict Content-Security-Policy: the Jinja workbench uses inline <script>
# blocks and a CSP without 'unsafe-inline' would break the UI.
SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"SAMEORIGIN"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-xss-protection", b"0"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
]

_MAX_REQUEST_ID_LEN = 128


def new_request_id() -> str:
    return uuid.uuid4().hex


class ObservabilityMiddleware:
    """Assigns a request id, injects security + correlation headers, and logs
    one structured access line per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        inbound = headers.get(b"x-request-id")
        request_id = (
            inbound.decode("latin-1")[:_MAX_REQUEST_ID_LEN]
            if inbound
            else new_request_id()
        )
        # Make request.state.request_id available to handlers + exception handler.
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        status_code = {"value": 0}
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code["value"] = message["status"]
                raw_headers = list(message.get("headers") or [])
                present = {k.lower() for k, _ in raw_headers}
                for name, value in SECURITY_HEADERS:
                    if name not in present:
                        raw_headers.append((name, value))
                if b"x-request-id" not in present:
                    raw_headers.append(
                        (b"x-request-id", request_id.encode("latin-1"))
                    )
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Will be turned into a 500 by ServerErrorMiddleware (outer). Log it
            # accurately here, then re-raise so the envelope handler still runs.
            status_code["value"] = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "%s %s -> %s %.1fms rid=%s",
                scope.get("method", "?"),
                scope.get("path", "?"),
                status_code["value"] or "-",
                duration_ms,
                request_id,
            )


class RateLimitMiddleware:
    """Per-client-IP sliding-window token bucket. No-op unless enabled.

    Lightweight + dependency-free; intended as a safety valve (e.g. to avoid
    accidentally hammering the free-tier LLM keys), not a hostile-traffic
    defence. State is in-process (single-worker local app)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        per_minute: int,
        burst: int,
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.capacity = max(1, burst)
        self.refill_per_sec = max(per_minute, 1) / 60.0
        # client -> (tokens, last_refill_ts)
        self._buckets: dict[str, list[float]] = defaultdict(
            lambda: [float(self.capacity), 0.0]
        )

    def _client_key(self, scope: Scope) -> str:
        client = scope.get("client")
        return client[0] if client else "unknown"

    def _allow(self, key: str, now: float) -> bool:
        bucket = self._buckets[key]
        tokens, last = bucket
        if last == 0.0:
            last = now
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
        if tokens < 1.0:
            bucket[0], bucket[1] = tokens, now
            return False
        bucket[0], bucket[1] = tokens - 1.0, now
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        key = self._client_key(scope)
        if self._allow(key, time.monotonic()):
            await self.app(scope, receive, send)
            return

        request_id = (scope.get("state") or {}).get("request_id", "")
        body = (
            b'{"error":{"type":"rate_limited",'
            b'"message":"Too many requests; slow down.",'
            b'"request_id":"' + request_id.encode("latin-1") + b'"}}'
        )
        headers = [
            (b"content-type", b"application/json"),
            (b"retry-after", b"1"),
        ]
        await send({"type": "http.response.start", "status": 429, "headers": headers})
        await send({"type": "http.response.body", "body": body})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_observability.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/middleware.py tests/test_hardening_observability.py
git commit -m "feat(phase-15): pure-ASGI observability middleware (request-id, access log, security headers)"
```

---

### Task 3: Consistent error envelope for unhandled exceptions

**Files:**
- Create: `app/errors.py`
- Test: `tests/test_hardening_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardening_errors.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.errors'`.

- [ ] **Step 3: Create `app/errors.py`**

```python
"""Global exception handling (Phase 15).

Only UNHANDLED exceptions (-> 500) are reshaped, into a JSON envelope with a
correlation id and no internal detail. FastAPI's HTTPException and validation
(422) responses are intentionally left at their defaults so existing API
contracts/tests are unaffected.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.middleware import SECURITY_HEADERS

logger = logging.getLogger(__name__)


def _security_header_dict() -> dict[str, str]:
    return {k.decode("latin-1"): v.decode("latin-1") for k, v in SECURITY_HEADERS}


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    # Full detail to the server log (with correlation id); nothing leaked to client.
    logger.exception("Unhandled exception rid=%s path=%s", request_id, request.url.path)
    headers = _security_header_dict()
    if request_id:
        headers["x-request-id"] = request_id
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "Internal server error",
                "request_id": request_id,
            }
        },
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the unhandled-exception envelope handler on the app."""
    app.add_exception_handler(Exception, unhandled_exception_handler)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_errors.py -v`
Expected: PASS (2 tests).

> Note: `add_exception_handler(Exception, ...)` is serviced by Starlette's `ServerErrorMiddleware`. Because that middleware sits OUTSIDE `ObservabilityMiddleware`, the handler sets the security + `x-request-id` headers on its own `JSONResponse` (it cannot rely on the middleware for error responses). `request.state.request_id` is readable because the scope object is shared.

- [ ] **Step 5: Commit**

```bash
git add app/errors.py tests/test_hardening_errors.py
git commit -m "feat(phase-15): JSON error envelope for unhandled 500s (no stack-trace leak, request-id)"
```

---

### Task 4: Rate limit behaviour

**Files:**
- Modify: (none — `RateLimitMiddleware` was created in Task 2)
- Test: `tests/test_hardening_rate_limit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardening_rate_limit.py
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
    # 429 carries the envelope + correlation id (set by Observability)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        for _ in range(5):
            r = await c.get("/ping")
        if r.status_code == 429:
            assert r.json()["error"]["type"] == "rate_limited"
            assert r.headers.get("x-request-id")
```

- [ ] **Step 2: Run test to verify it fails (or passes — code exists)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_rate_limit.py -v`
Expected: PASS (the middleware was implemented in Task 2). If a test fails, fix `RateLimitMiddleware` in `app/middleware.py`.

- [ ] **Step 3: (only if failing) adjust the token-bucket math**

If `test_enabled_limiter_trips_after_burst` does not see a 429, ensure `_allow` starts the bucket full (`capacity` tokens) and that the first-call `last == 0.0` branch initialises `last` to `now` (so no spurious refill credits the bucket on the first hit).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_rate_limit.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_hardening_rate_limit.py
git commit -m "test(phase-15): cover rate-limit disabled-passthrough and 429-after-burst"
```

---

### Task 5: Readiness endpoint

**Files:**
- Modify: `app/api/health.py`
- Create: `app/services/indexing/warmup.py`
- Test: `tests/test_health_ready.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_health_ready.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_health_ready.py -v`
Expected: FAIL (`/ready` 404).

- [ ] **Step 3: Create `app/services/indexing/warmup.py`**

```python
"""Model warmup + readiness flag (Phase 15).

The first ingest/search lazily loads the sentence-transformer (+ NLI) models,
which is slow and CPU-bound. `warmup_models()` constructs the singletons once
(typically from a startup background thread) so the first real request is fast;
`models_ready()` lets /ready report warm state.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_models_ready = False


def models_ready() -> bool:
    return _models_ready


def mark_models_ready() -> None:
    global _models_ready
    _models_ready = True


def warmup_models() -> None:
    """Construct the embedding + chunking singletons (blocking; run in a thread).

    Safe to call repeatedly; failures are logged and swallowed so a warmup
    problem never crashes startup -- lazy load still happens on first use.
    """
    try:
        from app.services.document_service import (
            _get_chunking_service,
            _get_embedding_service,
        )

        _get_chunking_service()
        _get_embedding_service()
        mark_models_ready()
        logger.info("Model warmup complete")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Model warmup failed (will lazy-load on first use): %s", exc)
```

- [ ] **Step 4: Add `/ready` to `app/api/health.py`**

Replace the file contents with:

```python
"""Health + readiness endpoints (Phase 15)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session_factory
from app.services.indexing.warmup import models_ready

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness: the process is up and serving."""
    return {"status": "ok", "version": get_settings().app_version}


@router.get("/ready")
async def readiness_check():
    """Readiness: dependencies usable. DB ping is required; model warmth is
    advisory (lazy-loads on first use). Returns 503 if the DB is unreachable."""
    checks: dict[str, object] = {}
    db_ok = True
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised only on DB outage
        db_ok = False
        checks["database"] = f"error: {type(exc).__name__}"
    checks["models_warm"] = models_ready()
    payload = {"status": "ready" if db_ok else "not_ready", "checks": checks}
    return JSONResponse(status_code=200 if db_ok else 503, content=payload)
```

- [ ] **Step 5: Run tests + commit**

Run: `.venv/Scripts/python.exe -m pytest tests/test_health_ready.py -v`
Expected: PASS (2 tests).

```bash
git add app/api/health.py app/services/indexing/warmup.py tests/test_health_ready.py
git commit -m "feat(phase-15): /ready readiness probe (DB ping + model-warm flag) + warmup module"
```

---

### Task 6: Cold-start fix — offload model load off the event loop

**Files:**
- Modify: `app/services/document_service.py`
- Test: `tests/test_hardening_warmup.py` (extend)

**Background:** `process_documents_batch` runs via `asyncio.create_task` ON the event loop. Inside it (`document_service.py:167-189`), `_get_embedding_service()` (model load) and `embedding_svc.delete_document_chunks(...)` execute synchronously on the loop, freezing all other requests for the ~50s first-load. `index_chunks` is already offloaded via `asyncio.to_thread`. This task offloads the construction + delete too, and marks models ready when constructed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardening_warmup.py  (append)
import asyncio

import pytest


@pytest.mark.asyncio
async def test_warmup_marks_models_ready(monkeypatch):
    import app.services.indexing.warmup as warmup

    # Avoid loading real models: stub the singleton getters.
    monkeypatch.setattr(
        "app.services.document_service._get_chunking_service", lambda: object()
    )
    monkeypatch.setattr(
        "app.services.document_service._get_embedding_service", lambda: object()
    )
    warmup._models_ready = False
    await asyncio.to_thread(warmup.warmup_models)
    assert warmup.models_ready() is True


def test_document_service_exposes_async_embedding_getter():
    # The offload helper used by the ingest path must exist and be a coroutine fn.
    import inspect

    from app.services import document_service as ds

    assert hasattr(ds, "_get_embedding_service_async")
    assert inspect.iscoroutinefunction(ds._get_embedding_service_async)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_warmup.py -v`
Expected: FAIL (`_get_embedding_service_async` missing).

- [ ] **Step 3: Offload in `app/services/document_service.py`**

Add near the other getters (after `_get_embedding_service`):

```python
async def _get_embedding_service_async() -> EmbeddingService:
    """Construct/return the embedding singleton OFF the event loop.

    The first construction loads the sentence-transformer model (CPU + network
    for HF Hub metadata), which would otherwise block the event loop and make
    the whole server unresponsive during the first ingest (observed ~50s)."""
    svc = await asyncio.to_thread(_get_embedding_service)
    try:
        from app.services.indexing.warmup import mark_models_ready

        mark_models_ready()
    except Exception:  # pragma: no cover - defensive
        pass
    return svc
```

Then in `process_documents_batch`, replace the indexing block (currently around lines 166-189) so the model load + Chroma delete run off-loop:

```python
                        try:
                            chunking_svc = _get_chunking_service()
                            # Model load happens off the event loop (cold start
                            # would otherwise freeze the server ~50s).
                            embedding_svc = await _get_embedding_service_async()

                            # Delete any existing chunks (re-upload case) -- Chroma
                            # I/O, also off the loop.
                            await asyncio.to_thread(
                                embedding_svc.delete_document_chunks,
                                project_id,
                                doc_id,
                            )

                            # Chunk the parsed document (CPU-light text split).
                            chunks = chunking_svc.chunk_document(
                                document_id=doc_id,
                                pages=parsed.pages,
                                filename=filename,
                            )

                            # Index chunks into ChromaDB (CPU-bound embedding).
                            if chunks:
                                chunk_count = await asyncio.to_thread(
                                    embedding_svc.index_chunks,
                                    project_id,
                                    chunks,
                                )
                                logger.info(
                                    "Indexed %d chunks for %s (doc_id=%d)",
                                    chunk_count,
                                    filename,
                                    doc_id,
                                )

                                try:
                                    from app.api.search import _get_search_service

                                    _get_search_service().invalidate_keyword_index(
                                        project_id
                                    )
                                except Exception as inv_exc:  # pragma: no cover
                                    logger.debug(
                                        "Keyword index invalidation skipped: %s",
                                        inv_exc,
                                    )
```

(Keep the metadata-enrichment + `await db.commit()` + `except Exception as idx_exc` tail of the block exactly as it is.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_warmup.py -v`
Expected: PASS.

Then run the indexing/document tests to ensure no regression:
Run: `.venv/Scripts/python.exe -m pytest tests/ -k "document or index or search or upload" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/document_service.py tests/test_hardening_warmup.py
git commit -m "fix(phase-15): load embedding model off the event loop during ingest (no cold-start freeze)"
```

---

### Task 7: Wire it all into the app

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_hardening_app_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardening_app_wiring.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_app_wiring.py -v`
Expected: FAIL (no security headers / no `/ready`).

- [ ] **Step 3: Wire `app/main.py`**

(a) Add imports near the top (after existing imports):

```python
from app.errors import register_exception_handlers
from app.middleware import ObservabilityMiddleware, RateLimitMiddleware
```

(b) In `lifespan`, after the directory-creation block and before `yield`, add the opt-in warmup (non-blocking — fire a background thread so startup stays fast):

```python
    if settings.warmup_models_on_startup:
        import asyncio

        from app.services.indexing.warmup import warmup_models

        asyncio.create_task(asyncio.to_thread(warmup_models))
        logger.info("Model warmup scheduled (background)")
```

(c) Use the single version source in the `FastAPI(...)` constructor:

```python
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)
```

(d) Register exception handlers immediately after the app is created:

```python
register_exception_handlers(app)
```

(e) Wire middleware so the final outer→inner order is `Observability → RateLimit → CORS`. The existing `CORSMiddleware` is added first (innermost of the three); ADD the two new ones AFTER it (so they end up outer). Replace the CORS block region with:

```python
# CORS (local dev: allow all). Added first => innermost of the custom stack.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (off by default; safety valve for the free-tier LLM keys).
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    per_minute=settings.rate_limit_per_minute,
    burst=settings.rate_limit_burst,
)

# Observability OUTERMOST: assigns the request id (so RateLimit's 429 can carry
# it), injects security + correlation headers, logs one line per request.
app.add_middleware(ObservabilityMiddleware)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_hardening_app_wiring.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Full suite green**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: ALL PASS (306 prior + the new Phase-15 tests). Investigate + fix any regression (most likely a test that asserted on a missing header or the page-smoke tests — those should be unaffected since HTTPException shapes are unchanged).

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_hardening_app_wiring.py
git commit -m "feat(phase-15): wire observability + rate-limit middleware, error handlers, /ready, opt-in warmup"
```

---

## Self-Review (run after writing the plan)

**Spec coverage:**
- Structured logging + request correlation → Task 2 (`ObservabilityMiddleware`).
- Security headers → Task 2.
- Consistent error envelope (no leak) → Task 3.
- Readiness probe → Task 5.
- Rate limiting (configurable) → Tasks 1+2+4.
- Cold-start event-loop freeze (real shakedown finding) → Task 6.
- Wiring + no-regression → Task 7.
- **Explicitly OUT of scope:** authentication/RBAC (user decision); CORS tightening (left as-is to avoid breaking local access — note as a future item); strict CSP (would break the inline-script Jinja UI).

**Type/name consistency:** `SECURITY_HEADERS` is `list[tuple[bytes, bytes]]` shared by middleware (raw ASGI form) and `errors.py` (decoded to `dict[str,str]` for `JSONResponse`). `request.state.request_id` set in `ObservabilityMiddleware`, read in `errors.py` + access log. `_get_embedding_service_async` defined in Task 6, used in Task 6's ingest edit. `models_ready`/`mark_models_ready`/`warmup_models` in `warmup.py`, used by `health.py` (Task 5), `document_service.py` (Task 6), `main.py` (Task 7).

**Placeholder scan:** none — every step has complete code.

**Risk notes for the implementer:**
- Verify middleware order empirically (the wiring test checks a header is present, but also confirm a tripped 429 carries `x-request-id` end-to-end).
- Confirm the SSE `/progress` endpoint and a file-download endpoint (e.g. `/api/suppliers/export`) still stream correctly through `ObservabilityMiddleware` (a quick manual or added test). This is the single most important correctness check — it's why the middleware is pure-ASGI.
- `httpx.ASGITransport(..., raise_app_exceptions=False)` is REQUIRED in the error-envelope test, else httpx re-raises the app exception instead of returning the 500.
