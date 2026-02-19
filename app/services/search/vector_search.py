"""ChromaDB semantic similarity search.

Wraps the EmbeddingService to provide semantic (vector) search queries
against per-project ChromaDB collections. Queries are normalized with
the same normalize_for_search() used at indexing time, ensuring
consistent matching across Arabic and English text.

Key design decisions:
- Query normalization matches index normalization (Pitfall 6 from RESEARCH).
- Empty collections return empty results gracefully (no 500 errors).
- Language filtering via ChromaDB ``where`` clause when specified.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.text_processing import normalize_for_search

if TYPE_CHECKING:
    from app.services.indexing.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Semantic similarity search using ChromaDB vector collections.

    Wraps the EmbeddingService to query per-project ChromaDB collections
    with normalized queries, returning ranked results by cosine distance.

    Args:
        embedding_service: The EmbeddingService instance managing ChromaDB
            collections and embedding generation.
    """

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service

    def search(
        self,
        project_id: int,
        query: str,
        n_results: int = 20,
        language_filter: str | None = None,
    ) -> list[tuple[str, str, dict, float]]:
        """Search a project's ChromaDB collection by semantic similarity.

        Normalizes the query the same way as indexed text (Arabic
        normalization, lowercase) and queries the collection for the
        closest embeddings by cosine distance.

        Args:
            project_id: Database ID of the project to search.
            query: User's search query text.
            n_results: Maximum number of results to return.
            language_filter: Optional language code ("ar", "en") to filter
                results by detected language.

        Returns:
            List of (chunk_id, document_text, metadata_dict, distance_score)
            tuples sorted by distance (ascending -- lower is more similar).
            Returns empty list if collection is empty or doesn't exist.
        """
        # CRITICAL: normalize query the same way as indexed text (Pitfall 6).
        normalized_query = normalize_for_search(query)

        try:
            collection = self._embedding_service.get_collection(project_id)
        except Exception as exc:
            logger.warning(
                "Could not get collection for project %d: %s",
                project_id,
                exc,
            )
            return []

        # Check if collection has any documents.
        if collection.count() == 0:
            logger.debug("Empty collection for project %d", project_id)
            return []

        # Build optional language filter.
        where = None
        if language_filter:
            where = {"language": language_filter}

        try:
            results = collection.query(
                query_texts=[normalized_query],
                n_results=min(n_results, collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error(
                "ChromaDB query failed for project %d: %s",
                project_id,
                exc,
            )
            return []

        # Unpack ChromaDB result format (lists of lists, one per query).
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        output: list[tuple[str, str, dict, float]] = []
        for chunk_id, doc_text, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            output.append((chunk_id, doc_text, metadata, distance))

        logger.debug(
            "Vector search for project %d returned %d results",
            project_id,
            len(output),
        )
        return output
