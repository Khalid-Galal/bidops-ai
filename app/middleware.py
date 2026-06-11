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
from collections import defaultdict

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
