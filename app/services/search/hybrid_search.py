"""Reciprocal Rank Fusion (RRF) hybrid search combining keyword and semantic.

Fuses BM25 keyword search results with ChromaDB vector similarity results
using Reciprocal Rank Fusion. This produces better relevance than either
method alone: keyword search catches exact term matches, while semantic
search finds conceptually related content across languages.

RRF formula per chunk:
    score = alpha / (rrf_k + semantic_rank + 1)
          + (1 - alpha) / (rrf_k + keyword_rank + 1)

Chunks appearing in only one result set receive score from that list only.

Key design decisions:
- Over-retrieval (top_k * 3) before fusion for better recall.
- alpha=0.7 default weights semantic search higher (better for multilingual).
- rrf_k=60 is the standard constant from the original RRF paper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.services.search.keyword_search import KeywordSearchService
from app.services.search.vector_search import VectorSearchService

if TYPE_CHECKING:
    from app.services.indexing.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result with combined relevance score and metadata.

    Attributes:
        chunk_id: Unique chunk identifier (e.g., "42_p3_c0").
        text: The chunk text for display to the user.
        score: Combined RRF relevance score (higher is more relevant).
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
    section_name: str | None


class HybridSearchService:
    """Combines BM25 keyword and vector semantic search via RRF fusion.

    Provides three search modes:
    - "hybrid": Fuses keyword and semantic results with RRF (default).
    - "semantic": Only vector similarity search.
    - "keyword": Only BM25 keyword search.

    Args:
        embedding_service: The EmbeddingService for ChromaDB access.
        alpha: Weight for semantic search in RRF (0.0-1.0, default 0.7).
            Keyword weight is (1 - alpha).
        rrf_k: RRF constant (default 60, from original RRF paper).
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        alpha: float = 0.7,
        rrf_k: int = 60,
    ) -> None:
        self._embedding_service = embedding_service
        self._alpha = alpha
        self._rrf_k = rrf_k
        self._keyword_service = KeywordSearchService()
        self._vector_service = VectorSearchService(embedding_service)

    def search(
        self,
        project_id: int,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """Search a project's documents using the specified mode.

        Args:
            project_id: Database ID of the project to search.
            query: User's search query text.
            top_k: Maximum number of results to return.
            mode: Search mode -- "hybrid", "semantic", or "keyword".

        Returns:
            List of SearchResult objects sorted by relevance score
            descending. Returns empty list if no results found.
        """
        if mode == "semantic":
            return self._semantic_only(project_id, query, top_k)
        elif mode == "keyword":
            return self._keyword_only(project_id, query, top_k)
        else:
            return self._hybrid(project_id, query, top_k)

    def invalidate_keyword_index(self, project_id: int) -> None:
        """Invalidate the cached BM25 index for a project.

        Must be called after new documents are indexed for a project
        so the next keyword search uses fresh data.

        Args:
            project_id: Database ID of the project.
        """
        self._keyword_service.invalidate_index(project_id)

    def _semantic_only(
        self, project_id: int, query: str, top_k: int
    ) -> list[SearchResult]:
        """Run semantic-only search and return SearchResult list."""
        raw_results = self._vector_service.search(
            project_id, query, n_results=top_k
        )

        results: list[SearchResult] = []
        for chunk_id, doc_text, metadata, distance in raw_results:
            # Convert cosine distance to similarity score (1 - distance).
            similarity = max(0.0, 1.0 - distance)
            results.append(
                self._build_search_result(chunk_id, metadata, similarity)
            )

        return results

    def _keyword_only(
        self, project_id: int, query: str, top_k: int
    ) -> list[SearchResult]:
        """Run keyword-only search and return SearchResult list."""
        raw_results = self._keyword_service.search(
            project_id, query, self._embedding_service, top_k=top_k
        )

        if not raw_results:
            return []

        # Normalize BM25 scores to 0-1 range for consistent display.
        max_score = max(score for _, score, _, _ in raw_results)
        if max_score <= 0:
            return []

        results: list[SearchResult] = []
        for chunk_id, score, doc_text, metadata in raw_results:
            normalized_score = score / max_score
            results.append(
                self._build_search_result(chunk_id, metadata, normalized_score)
            )

        return results

    def _hybrid(
        self, project_id: int, query: str, top_k: int
    ) -> list[SearchResult]:
        """Run hybrid search with RRF fusion of keyword + semantic."""
        # Over-retrieve for better fusion recall.
        over_retrieve = top_k * 3

        semantic_results = self._vector_service.search(
            project_id, query, n_results=over_retrieve
        )
        keyword_results = self._keyword_service.search(
            project_id, query, self._embedding_service, top_k=over_retrieve
        )

        return self._rrf_fusion(semantic_results, keyword_results, top_k)

    def _rrf_fusion(
        self,
        semantic_results: list[tuple[str, str, dict, float]],
        keyword_results: list[tuple[str, float, str, dict]],
        top_k: int,
    ) -> list[SearchResult]:
        """Fuse semantic and keyword results using Reciprocal Rank Fusion.

        RRF formula per chunk:
            score = alpha / (rrf_k + semantic_rank + 1)
                  + (1 - alpha) / (rrf_k + keyword_rank + 1)

        Chunks in only one list get score from that list only.

        Args:
            semantic_results: From VectorSearchService.search().
                Format: [(chunk_id, doc_text, metadata, distance), ...]
            keyword_results: From KeywordSearchService.search().
                Format: [(chunk_id, bm25_score, doc_text, metadata), ...]
            top_k: Maximum number of fused results to return.

        Returns:
            List of SearchResult sorted by combined RRF score descending.
        """
        alpha = self._alpha
        rrf_k = self._rrf_k

        # Build rank maps (0-indexed ranks).
        semantic_rank: dict[str, int] = {}
        semantic_meta: dict[str, dict] = {}
        for rank, (chunk_id, doc_text, metadata, distance) in enumerate(
            semantic_results
        ):
            semantic_rank[chunk_id] = rank
            semantic_meta[chunk_id] = metadata

        keyword_rank: dict[str, int] = {}
        keyword_meta: dict[str, dict] = {}
        for rank, (chunk_id, score, doc_text, metadata) in enumerate(
            keyword_results
        ):
            keyword_rank[chunk_id] = rank
            keyword_meta[chunk_id] = metadata

        # Collect all unique chunk IDs.
        all_chunk_ids = set(semantic_rank.keys()) | set(keyword_rank.keys())

        # Calculate RRF scores.
        scored: list[tuple[str, float, dict]] = []
        for chunk_id in all_chunk_ids:
            rrf_score = 0.0

            if chunk_id in semantic_rank:
                rrf_score += alpha / (rrf_k + semantic_rank[chunk_id] + 1)

            if chunk_id in keyword_rank:
                rrf_score += (1 - alpha) / (rrf_k + keyword_rank[chunk_id] + 1)

            # Prefer semantic metadata (has original text), fall back to keyword.
            metadata = semantic_meta.get(chunk_id) or keyword_meta.get(
                chunk_id, {}
            )
            scored.append((chunk_id, rrf_score, metadata))

        # Sort by RRF score descending and take top_k.
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]

        # Build SearchResult objects.
        results: list[SearchResult] = []
        for chunk_id, rrf_score, metadata in scored:
            results.append(
                self._build_search_result(chunk_id, metadata, rrf_score)
            )

        logger.debug(
            "RRF fusion: %d semantic + %d keyword -> %d results",
            len(semantic_results),
            len(keyword_results),
            len(results),
        )
        return results

    @staticmethod
    def _build_search_result(
        chunk_id: str, metadata: dict, score: float
    ) -> SearchResult:
        """Build a SearchResult from chunk metadata.

        Args:
            chunk_id: The chunk identifier.
            metadata: ChromaDB metadata dict for the chunk.
            score: Relevance score (RRF, similarity, or normalized BM25).

        Returns:
            A populated SearchResult dataclass.
        """
        return SearchResult(
            chunk_id=chunk_id,
            text=metadata.get("text", ""),
            score=score,
            document_id=int(metadata.get("document_id", 0)),
            page_number=int(metadata.get("page_number", 0)),
            language=metadata.get("language", "unknown"),
            filename=metadata.get("filename", ""),
            chunk_type=metadata.get("chunk_type", "text"),
            section_name=metadata.get("section_name") or None,
        )
