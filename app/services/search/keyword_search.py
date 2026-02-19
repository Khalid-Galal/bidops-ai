"""BM25 keyword search with Arabic normalization.

Provides BM25Okapi keyword search that builds an in-memory inverted index
from a project's ChromaDB collection. The index is lazily built on first
search and cached per project. Index invalidation is exposed for callers
to trigger after new documents are indexed.

Key design decisions:
- Tokenization uses normalize_for_search() + split() to match the
  normalization applied to indexed text (Pitfall 6 from RESEARCH).
- Lazy index building: index is created on first search per project.
- Cache invalidation: invalidate_index() must be called after new
  documents are added (Pitfall 4 from RESEARCH).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from rank_bm25 import BM25Okapi

from app.services.text_processing import normalize_for_search

if TYPE_CHECKING:
    from app.services.indexing.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class KeywordSearchService:
    """BM25 keyword search over project document chunks.

    Builds a BM25Okapi index from all chunks in a project's ChromaDB
    collection. The index is cached per project and must be invalidated
    when new documents are added.
    """

    def __init__(self) -> None:
        # Cache: project_id -> (bm25, chunk_ids, documents, metadatas)
        self._indices: dict[
            int, tuple[BM25Okapi, list[str], list[str], list[dict]]
        ] = {}

    def build_index(
        self, project_id: int, embedding_service: EmbeddingService
    ) -> None:
        """Build (or rebuild) the BM25 index for a project.

        Fetches ALL chunks from the project's ChromaDB collection and
        creates a BM25Okapi index from the normalized document texts.

        Args:
            project_id: Database ID of the project.
            embedding_service: EmbeddingService to access the ChromaDB
                collection.
        """
        try:
            collection = embedding_service.get_collection(project_id)
        except Exception as exc:
            logger.warning(
                "Could not get collection for BM25 index (project %d): %s",
                project_id,
                exc,
            )
            return

        count = collection.count()
        if count == 0:
            logger.debug("Empty collection for project %d, no BM25 index", project_id)
            return

        # Fetch all documents from ChromaDB.
        all_data = collection.get(include=["documents", "metadatas"])

        chunk_ids: list[str] = all_data.get("ids", [])
        documents: list[str] = all_data.get("documents", [])
        metadatas: list[dict] = all_data.get("metadatas", [])

        if not documents:
            logger.debug("No documents in collection for project %d", project_id)
            return

        # Tokenize: normalize_for_search() then split on whitespace.
        # Documents are already stored normalized in ChromaDB, but we
        # re-normalize to be safe (idempotent operation).
        tokenized_docs = [
            normalize_for_search(doc).split() for doc in documents
        ]

        # Filter out empty tokenizations (would cause BM25 issues).
        valid_indices = [i for i, tokens in enumerate(tokenized_docs) if tokens]
        if not valid_indices:
            logger.debug("No tokenizable content for project %d", project_id)
            return

        tokenized_docs = [tokenized_docs[i] for i in valid_indices]
        chunk_ids = [chunk_ids[i] for i in valid_indices]
        documents = [documents[i] for i in valid_indices]
        metadatas = [metadatas[i] for i in valid_indices]

        bm25 = BM25Okapi(tokenized_docs)

        self._indices[project_id] = (bm25, chunk_ids, documents, metadatas)
        logger.info(
            "Built BM25 index for project %d: %d chunks",
            project_id,
            len(chunk_ids),
        )

    def invalidate_index(self, project_id: int) -> None:
        """Remove the cached BM25 index for a project.

        MUST be called whenever new documents are indexed for the project,
        so the next search triggers a fresh index build (Pitfall 4).

        Args:
            project_id: Database ID of the project whose index to invalidate.
        """
        if project_id in self._indices:
            del self._indices[project_id]
            logger.info("Invalidated BM25 index for project %d", project_id)

    def search(
        self,
        project_id: int,
        query: str,
        embedding_service: EmbeddingService,
        top_k: int = 20,
    ) -> list[tuple[str, float, str, dict]]:
        """Search a project's chunks by BM25 keyword relevance.

        Lazily builds the BM25 index on first search for a project.
        Tokenizes the query using the same normalization as the indexed
        documents.

        Args:
            project_id: Database ID of the project to search.
            query: User's search query text.
            embedding_service: EmbeddingService to access the ChromaDB
                collection (used for lazy index building).
            top_k: Maximum number of results to return.

        Returns:
            List of (chunk_id, bm25_score, document_text, metadata_dict)
            tuples sorted by BM25 score descending. Only results with
            score > 0 are included.
        """
        # Lazily build index if not cached.
        if project_id not in self._indices:
            self.build_index(project_id, embedding_service)

        if project_id not in self._indices:
            # Index build failed or collection is empty.
            return []

        bm25, chunk_ids, documents, metadatas = self._indices[project_id]

        # CRITICAL: tokenize query the same way as documents.
        tokenized_query = normalize_for_search(query).split()
        if not tokenized_query:
            return []

        # Get BM25 scores for all documents.
        scores = bm25.get_scores(tokenized_query)

        # Sort by score descending, take top_k where score > 0.
        scored_indices = np.argsort(scores)[::-1]

        results: list[tuple[str, float, str, dict]] = []
        for idx in scored_indices:
            score = float(scores[idx])
            if score <= 0:
                break
            if len(results) >= top_k:
                break
            results.append(
                (chunk_ids[idx], score, documents[idx], metadatas[idx])
            )

        logger.debug(
            "BM25 search for project %d returned %d results",
            project_id,
            len(results),
        )
        return results
