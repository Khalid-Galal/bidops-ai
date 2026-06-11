"""Phase 15: settings + model warmup."""
from __future__ import annotations

import asyncio

import pytest

from app.config import Settings


def test_hardening_settings_have_safe_defaults():
    s = Settings()
    # New NFR knobs exist with conservative defaults.
    assert s.app_version  # non-empty version string
    assert s.rate_limit_enabled is False          # off by default -> zero UX risk
    assert s.rate_limit_per_minute == 120          # lenient default when enabled
    assert s.rate_limit_burst == 30
    assert s.warmup_models_on_startup is False      # tests/pure-pricing users unaffected


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
