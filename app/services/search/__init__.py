"""Search services combining keyword (BM25) and semantic (vector) search.

Provides BM25 keyword search, ChromaDB vector similarity search, and a hybrid
search service that fuses both result sets using Reciprocal Rank Fusion (RRF)
for optimal relevance across bilingual Arabic/English content.

Usage:
    from app.services.search import (
        KeywordSearchService,
        VectorSearchService,
        HybridSearchService,
        SearchResult,
    )
"""

from app.services.search.hybrid_search import HybridSearchService, SearchResult
from app.services.search.keyword_search import KeywordSearchService
from app.services.search.vector_search import VectorSearchService

__all__ = [
    "KeywordSearchService",
    "VectorSearchService",
    "HybridSearchService",
    "SearchResult",
]
