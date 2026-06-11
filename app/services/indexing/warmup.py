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
