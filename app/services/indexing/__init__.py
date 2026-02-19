"""Document indexing services for chunking and vector embedding.

Provides semantic document chunking with Arabic-aware separators and
ChromaDB vector storage with multilingual embeddings for per-project
search collections.

Usage:
    from app.services.indexing import ChunkingService, DocumentChunk, EmbeddingService
"""

from app.services.indexing.chunking_service import ChunkingService, DocumentChunk
from app.services.indexing.embedding_service import EmbeddingService

__all__ = [
    "ChunkingService",
    "DocumentChunk",
    "EmbeddingService",
]
