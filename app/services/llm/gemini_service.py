"""Instructor-wrapped Gemini client with multi-key rotation for structured extraction.

Provides reliable structured output from Gemini with automatic Pydantic
validation (via instructor) and rotation across multiple API keys to work
around per-key free-tier rate limits. On a quota (429 RESOURCE_EXHAUSTED) or
disabled-key (403 PERMISSION_DENIED) error, the service rotates to the next
configured key and retries. Tenacity retry handles transient network errors only.
"""

from __future__ import annotations

import logging
import threading
from typing import TypeVar

import instructor
from google.genai.types import GenerateContentConfig, ThinkingConfig
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Low thinking budget: extraction/verification is verbatim lookup, not
# multi-step reasoning, so a large thinking budget just burns quota/latency.
_THINKING_BUDGET = 128

# Substrings identifying provider errors that should trigger rotation to the
# next API key (rather than failing the call outright).
_ROTATABLE_MARKERS = (
    "RESOURCE_EXHAUSTED",
    "429",
    "PERMISSION_DENIED",
    "reported as leaked",
    "exceeded your current quota",
    "quota",
)


def _is_rotatable_error(exc: Exception) -> bool:
    """True if the error indicates this key is rate-limited/disabled."""
    msg = str(exc)
    return any(marker in msg for marker in _ROTATABLE_MARKERS)


class GeminiService:
    """Gemini LLM service with structured output via instructor and key rotation.

    Uses instructor.from_provider("google/...") for automatic Pydantic
    validation and JSON schema enforcement. When multiple API keys are
    configured, calls are spread round-robin across keys and automatically
    fail over to the next key on quota/permission errors -- this works around
    the low per-key free-tier rate limits (e.g. 5 requests/minute).

    Clients are lazily initialized per key on first use.

    Args:
        api_key: A single Gemini API key (used only if ``api_keys`` is empty).
        model: Gemini model name (default: "gemini-2.5-pro").
        api_keys: Optional list of API keys enabling rotation/failover.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.5-pro",
        api_keys: list[str] | None = None,
        temperature: float | None = None,
    ) -> None:
        keys = [k.strip() for k in (api_keys or []) if k and k.strip()]
        if not keys and api_key:
            keys = [api_key.strip()]
        if not keys:
            raise ValueError("GeminiService requires at least one API key")
        self._keys = keys
        self._model = model
        self._clients: dict[str, instructor.Instructor] = {}
        self._idx = 0
        self._lock = threading.Lock()
        self._temperature = (
            temperature if temperature is not None else get_settings().llm_temperature
        )
        self._generation_config = GenerateContentConfig(
            temperature=self._temperature,
            thinking_config=ThinkingConfig(thinking_budget=_THINKING_BUDGET),
        )

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def _client_for(self, key: str) -> instructor.Instructor:
        """Lazily build (and cache) the instructor client for a given key."""
        client = self._clients.get(key)
        if client is None:
            client = instructor.from_provider(
                f"google/{self._model}",
                api_key=key,
            )
            self._clients[key] = client
        return client

    def _next_start(self) -> int:
        """Round-robin starting index to spread load across keys (thread-safe)."""
        with self._lock:
            start = self._idx
            self._idx = (self._idx + 1) % len(self._keys)
        return start

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def extract(
        self,
        prompt: str,
        response_model: type[T],
        max_retries: int = 3,
    ) -> T:
        """Extract structured data, rotating keys on quota/permission errors.

        Tries each configured key (starting at a round-robin offset) until one
        succeeds. A quota/permission error on one key triggers failover to the
        next; the last error is raised only if every key fails. Per-key
        validation retries are kept low (fail-fast) so an exhausted key does not
        waste its quota before rotation.

        Args:
            prompt: The extraction prompt with context.
            response_model: Pydantic model class for the expected response.
            max_retries: Per-key instructor validation retries (kept small).

        Returns:
            An instance of ``response_model`` validated by instructor.

        Raises:
            Exception: If extraction fails on every configured key.
        """
        n = len(self._keys)
        start = self._next_start()
        per_key_retries = max(1, min(max_retries, 1))  # fail fast; rotation is the real retry
        last_exc: Exception | None = None

        for offset in range(n):
            key_index = (start + offset) % n
            key = self._keys[key_index]
            try:
                return self._client_for(key).create(
                    messages=[{"role": "user", "content": prompt}],
                    response_model=response_model,
                    max_retries=per_key_retries,
                    config=self._generation_config,
                )
            except (ConnectionError, TimeoutError):
                # Transient network error -- let tenacity retry the whole call.
                raise
            except Exception as exc:  # noqa: BLE001
                if _is_rotatable_error(exc) and offset < n - 1:
                    last_exc = exc
                    logger.warning(
                        "Gemini key #%d rate-limited/disabled; rotating to next key",
                        key_index,
                    )
                    continue
                logger.exception(
                    "Gemini extraction failed for model %s",
                    response_model.__name__,
                )
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Gemini extraction failed: no keys available")
