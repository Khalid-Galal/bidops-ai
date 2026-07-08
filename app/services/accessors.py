"""Cached singleton accessors for the search/LLM service stack.

Collapses the wiring that used to be copy-pasted across app/api/search.py,
app/api/checklist.py, app/api/extraction.py, and
app/services/packaging/document_linker.py (which imported the singleton
straight out of app/api/search.py -- the codebase's only api->services
dependency inversion) into one place. Callers just import get_x() from here.

Nothing here does eager work: services are constructed lazily on first call
so the app still starts up (and degrades gracefully) with no Gemini key.
"""

from __future__ import annotations

from app.config import get_settings
from app.services.extraction.citation_verifier import CitationVerifier
from app.services.indexing.embedding_service import EmbeddingService
from app.services.llm.gemini_service import GeminiService
from app.services.search.hybrid_search import HybridSearchService

_embedding_service: EmbeddingService | None = None
_search_service: HybridSearchService | None = None
_llm_service: GeminiService | None = None
_citation_verifier: CitationVerifier | None = None


def get_search_service() -> HybridSearchService:
    """Get or create the HybridSearchService singleton.

    Lazily initializes the EmbeddingService and HybridSearchService on
    first call to avoid startup cost when search is not used.
    """
    global _embedding_service, _search_service
    if _search_service is None:
        settings = get_settings()
        if _embedding_service is None:
            _embedding_service = EmbeddingService(
                persist_dir=settings.chroma_persist_dir,
                model_name=settings.embedding_model,
            )
        _search_service = HybridSearchService(embedding_service=_embedding_service)
    return _search_service


def get_llm_service() -> GeminiService:
    """Get or create the GeminiService singleton.

    Caller is responsible for checking `settings.gemini_key_list()` is
    non-empty before calling this (the LLM stack is never constructed
    when no key is configured).
    """
    global _llm_service
    if _llm_service is None:
        settings = get_settings()
        _llm_service = GeminiService(
            api_keys=settings.gemini_key_list(),
            model=settings.gemini_model,
        )
    return _llm_service


def get_citation_verifier() -> CitationVerifier:
    """Get or create the CitationVerifier (NLI cross-encoder) singleton."""
    global _citation_verifier
    if _citation_verifier is None:
        settings = get_settings()
        _citation_verifier = CitationVerifier(
            model_name=settings.nli_model,
            confidence_high=settings.confidence_high_threshold,
            confidence_low=settings.confidence_low_threshold,
            review_threshold=settings.review_threshold,
        )
    return _citation_verifier
