"""ChromaDB vector storage with multilingual embeddings.

Manages per-project ChromaDB collections for semantic document search.
Each project gets its own collection, allowing independent search scopes
and easy cleanup on project deletion.

Key design decisions:
- Lazy initialization: ChromaDB client and embedding model are loaded on
  first use to avoid startup cost (~420MB model download on first run).
- upsert() instead of add(): Ensures idempotency -- re-indexing the same
  document won't create duplicate chunks.
- delete_document_chunks() before re-indexing: Prevents orphan chunks when
  a document is re-uploaded (old chunks with different IDs would persist).
- Per-project collections: Isolates search scope and allows atomic project
  deletion without affecting other projects.
- Cosine similarity: Best for multilingual embeddings where magnitude varies
  across languages.

Pitfalls addressed (from 02-RESEARCH.md):
- Pitfall 3: Always pass embedding_function to get_or_create_collection()
  to avoid dimension mismatch on collection reopening.
- Pitfall 7: Delete old chunks before re-indexing to avoid stale results.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import chromadb

from app.services.indexing.chunking_service import DocumentChunk

logger = logging.getLogger(__name__)

# ChromaDB batch size limit for upsert operations.
_CHROMA_MAX_BATCH_SIZE = 5000


class EmbeddingService:
    """Manages ChromaDB vector collections with multilingual embeddings.

    Provides per-project collections for storing and retrieving document
    chunk embeddings. Uses sentence-transformers' multilingual model for
    embedding generation.

    Args:
        persist_dir: Directory path for ChromaDB persistent storage.
        model_name: Name of the sentence-transformers model to use.
    """

    def __init__(self, persist_dir: str, model_name: str) -> None:
        self._persist_dir = persist_dir
        self._model_name = model_name
        self._client: chromadb.ClientAPI | None = None
        self._ef = None  # SentenceTransformerEmbeddingFunction

    def _get_client(self) -> chromadb.ClientAPI:
        """Get or create the ChromaDB persistent client.

        Lazy-initializes on first call to avoid startup cost when the
        embedding service is not needed (e.g., during document listing).

        Returns:
            A chromadb.PersistentClient instance.
        """
        if self._client is not None:
            return self._client

        import chromadb

        self._client = chromadb.PersistentClient(path=self._persist_dir)
        logger.info("ChromaDB client initialized at %s", self._persist_dir)
        return self._client

    def _get_embedding_function(self):
        """Get or create the sentence-transformer embedding function.

        Lazy-initializes on first call. The model (~420MB) is downloaded
        automatically on first use and cached locally by sentence-transformers.

        Returns:
            A SentenceTransformerEmbeddingFunction instance.
        """
        if self._ef is not None:
            return self._ef

        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        self._ef = SentenceTransformerEmbeddingFunction(
            model_name=self._model_name,
            device="cpu",
            normalize_embeddings=True,
        )
        logger.info("Embedding model loaded: %s", self._model_name)
        return self._ef

    def get_collection(self, project_id: int) -> chromadb.Collection:
        """Get or create the ChromaDB collection for a project.

        CRITICAL: Always passes embedding_function to avoid dimension
        mismatch when reopening an existing collection (Pitfall 3).

        Args:
            project_id: Database ID of the project.

        Returns:
            A chromadb.Collection configured with cosine similarity.
        """
        client = self._get_client()
        ef = self._get_embedding_function()

        return client.get_or_create_collection(
            name=f"project_{project_id}",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks(
        self, project_id: int, chunks: list[DocumentChunk]
    ) -> int:
        """Add document chunks to the project's ChromaDB collection.

        Uses upsert() for idempotency -- re-indexing the same chunks
        updates them rather than creating duplicates. The ``text_normalized``
        field is embedded (not the raw text) to ensure consistent matching
        with normalized queries.

        Args:
            project_id: Database ID of the project.
            chunks: List of DocumentChunk objects to index.

        Returns:
            Number of chunks indexed.
        """
        if not chunks:
            return 0

        collection = self.get_collection(project_id)

        # Prepare data for upsert.
        ids = [c.chunk_id for c in chunks]
        documents = [c.text_normalized for c in chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "page_number": c.page_number,
                "language": c.language,
                "chunk_type": c.chunk_type,
                "section_name": c.section_name or "",
                "char_start": c.char_start,
                "char_end": c.char_end,
                "filename": c.metadata.get("filename", ""),
                "text": c.text,  # Store original text for display
            }
            for c in chunks
        ]

        # Upsert in batches to respect ChromaDB's batch size limit.
        total_indexed = 0
        for i in range(0, len(ids), _CHROMA_MAX_BATCH_SIZE):
            batch_end = min(i + _CHROMA_MAX_BATCH_SIZE, len(ids))
            collection.upsert(
                ids=ids[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )
            total_indexed += batch_end - i

        logger.info(
            "Indexed %d chunks into project_%d collection",
            total_indexed,
            project_id,
        )
        return total_indexed

    def delete_document_chunks(
        self, project_id: int, document_id: int
    ) -> None:
        """Delete all chunks for a specific document from the collection.

        MUST be called before re-indexing a document to prevent orphan
        chunks (Pitfall 7). Old chunks with different IDs would persist
        alongside new chunks, causing duplicate/stale search results.

        Args:
            project_id: Database ID of the project.
            document_id: Database ID of the document whose chunks to delete.
        """
        try:
            collection = self.get_collection(project_id)
            collection.delete(where={"document_id": document_id})
            logger.info(
                "Deleted chunks for document %d from project_%d",
                document_id,
                project_id,
            )
        except Exception as exc:
            # Collection may not exist yet (first indexing) -- not an error.
            logger.debug(
                "Could not delete chunks for document %d from project_%d: %s",
                document_id,
                project_id,
                exc,
            )

    def delete_collection(self, project_id: int) -> None:
        """Delete an entire project collection.

        Used when a project is deleted to clean up all vector data.

        Args:
            project_id: Database ID of the project.
        """
        client = self._get_client()
        try:
            client.delete_collection(name=f"project_{project_id}")
            logger.info("Deleted collection project_%d", project_id)
        except Exception as exc:
            logger.debug(
                "Could not delete collection project_%d: %s",
                project_id,
                exc,
            )

    def get_collection_count(self, project_id: int) -> int:
        """Return the number of chunks in a project's collection.

        Args:
            project_id: Database ID of the project.

        Returns:
            Number of chunks (documents) stored in the collection.
            Returns 0 if the collection does not exist.
        """
        try:
            collection = self.get_collection(project_id)
            return collection.count()
        except Exception:
            return 0
