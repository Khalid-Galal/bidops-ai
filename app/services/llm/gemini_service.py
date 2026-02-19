"""Instructor-wrapped Gemini client for structured extraction.

Provides reliable structured output from Gemini with automatic
Pydantic validation and retry-on-validation-failure via instructor.
Tenacity retry handles transient network errors only -- instructor
manages schema validation retries internally.
"""

from __future__ import annotations

import logging
from typing import TypeVar

import instructor
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiService:
    """Gemini LLM service with structured output via instructor.

    Uses instructor.from_provider("google/...") for automatic Pydantic
    validation, retry-on-validation-failure, and JSON schema enforcement.

    The client is lazily initialized on first use to avoid API calls
    during construction (useful for testing and configuration validation).

    Args:
        api_key: Gemini API key from Google AI Studio.
        model: Gemini model name (default: "gemini-2.5-pro").
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro") -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self) -> instructor.Instructor:
        """Lazily initialize the instructor-wrapped Gemini client."""
        if self._client is None:
            self._client = instructor.from_provider(
                f"google/{self._model}",
                api_key=self._api_key,
            )
        return self._client

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
        """Extract structured data from prompt using Gemini with instructor validation.

        Args:
            prompt: The extraction prompt with context.
            response_model: Pydantic model class for the expected response.
            max_retries: Number of instructor validation retries (default: 3).

        Returns:
            An instance of response_model validated by instructor.

        Raises:
            Exception: If extraction fails after all retries.
        """
        client = self._get_client()
        try:
            response = client.create(
                messages=[{"role": "user", "content": prompt}],
                response_model=response_model,
                max_retries=max_retries,
            )
            return response
        except (ConnectionError, TimeoutError):
            # Let tenacity handle transient network errors.
            raise
        except Exception:
            logger.exception(
                "Gemini extraction failed for model %s",
                response_model.__name__,
            )
            raise
