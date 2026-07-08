"""Tests for GeminiService generation config (finding 17).

Verifies that every ``create`` call is given a low, deterministic-leaning
temperature and a low thinking budget, sourced from settings by default and
overridable per instance. No real network/LLM calls are made -- the
instructor client is mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from app.services.llm.gemini_service import GeminiService


class _DummyModel(BaseModel):
    value: str = "ok"


def _make_service(**kwargs: object) -> tuple[GeminiService, MagicMock]:
    mock_client = MagicMock()
    mock_client.create.return_value = _DummyModel()
    with patch("instructor.from_provider", return_value=mock_client):
        svc = GeminiService(api_key="test-key", **kwargs)
        # Force lazy client creation now, under the same patch.
        svc._client_for("test-key")
    return svc, mock_client


def test_extract_passes_generation_config_with_default_temperature() -> None:
    svc, mock_client = _make_service()

    result = svc.extract("prompt", _DummyModel)

    assert result == _DummyModel()
    _, call_kwargs = mock_client.create.call_args
    config = call_kwargs["config"]
    assert config.temperature == 0.1  # settings default
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 128


def test_extract_uses_explicit_temperature_override() -> None:
    svc, mock_client = _make_service(temperature=0.4)

    svc.extract("prompt", _DummyModel)

    _, call_kwargs = mock_client.create.call_args
    assert call_kwargs["config"].temperature == 0.4


def test_extract_reuses_same_generation_config_across_calls() -> None:
    svc, mock_client = _make_service()

    svc.extract("prompt one", _DummyModel)
    svc.extract("prompt two", _DummyModel)

    first_config = mock_client.create.call_args_list[0].kwargs["config"]
    second_config = mock_client.create.call_args_list[1].kwargs["config"]
    assert first_config is second_config
