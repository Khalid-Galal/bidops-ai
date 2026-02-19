"""Pydantic schemas for the search API endpoint.

Defines request validation and response serialization models for the
hybrid search endpoint. SearchResultItem maps directly from the
SearchResult dataclass returned by HybridSearchService.
"""

from __future__ import annotations

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    """A single search result with relevance score and source metadata.

    Each result corresponds to a document chunk that matched the query,
    including enough metadata for the UI to display the match and link
    back to the source document page.

    Attributes:
        chunk_id: Unique chunk identifier (e.g., "42_p3_c0").
        text: The matching chunk text for display.
        score: Relevance score (0-1 range after RRF normalization).
        document_id: Foreign key to the Document table.
        page_number: 1-based source page number for citation.
        language: Detected language ("ar", "en", "mixed", "unknown").
        filename: Original document filename.
        chunk_type: Either "text" or "table".
        section_name: Detected section heading, or None.
    """

    chunk_id: str
    text: str
    score: float
    document_id: int
    page_number: int
    language: str
    filename: str
    chunk_type: str
    section_name: str | None = None


class SearchResponse(BaseModel):
    """Response wrapper for search results.

    Attributes:
        query: The original search query (for display in the UI).
        mode: Search mode used -- "hybrid", "semantic", or "keyword".
        total_results: Number of results returned.
        results: List of SearchResultItem objects.
    """

    query: str
    mode: str
    total_results: int
    results: list[SearchResultItem]
