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
