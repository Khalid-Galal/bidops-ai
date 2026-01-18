"""Vector store service for document embeddings using Qdrant."""

import hashlib
from typing import Optional
from uuid import uuid4

from app.config import get_settings

settings = get_settings()


class VectorStoreService:
    """Service for managing document embeddings in Qdrant.

    Provides methods for:
    - Creating and managing collections
    - Generating embeddings
    - Storing document chunks
    - Semantic search
    """

    def __init__(self):
        """Initialize vector store service."""
        self._client = None
        self._embeddings = None
        self.collection_name = settings.QDRANT_COLLECTION

    @property
    def client(self):
        """Lazy-load Qdrant client."""
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=settings.QDRANT_URL)
        return self._client

    @property
    def embeddings(self):
        """Lazy-load embeddings model."""
        if self._embeddings is None:
            if settings.OPENAI_API_KEY:
                from langchain_openai import OpenAIEmbeddings
                self._embeddings = OpenAIEmbeddings(
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    openai_api_key=settings.OPENAI_API_KEY,
                )
            else:
                # Fallback to local embeddings
                from sentence_transformers import SentenceTransformer
                self._embeddings = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embeddings

    async def ensure_collection(self) -> None:
        """Ensure the collection exists with proper configuration."""
        from qdrant_client.models import Distance, VectorParams

        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            # Create collection with OpenAI embedding dimensions
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=1536,  # OpenAI text-embedding-3-small dimensions
                    distance=Distance.COSINE,
                ),
            )

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if hasattr(self.embeddings, "embed_query"):
            # LangChain embeddings
            return self.embeddings.embed_query(text)
        else:
            # SentenceTransformer
            return self.embeddings.encode(text).tolist()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if hasattr(self.embeddings, "embed_documents"):
            # LangChain embeddings
            return self.embeddings.embed_documents(texts)
        else:
            # SentenceTransformer
            return self.embeddings.encode(texts).tolist()

    async def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: Optional[list[str]] = None,
    ) -> list[str]:
        """Add documents to the vector store.

        Args:
            texts: List of text content
            metadatas: List of metadata dictionaries
            ids: Optional list of IDs (generated if not provided)

        Returns:
            List of document IDs
        """
        from qdrant_client.models import PointStruct

        await self.ensure_collection()

        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid4()) for _ in texts]

        # Generate embeddings
        embeddings = await self.embed_texts(texts)

        # Create points
        points = [
            PointStruct(
                id=doc_id,
                vector=embedding,
                payload={"text": text, **metadata},
            )
            for doc_id, text, embedding, metadata in zip(ids, texts, embeddings, metadatas)
        ]

        # Upsert to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        return ids

    async def search(
        self,
        query: str,
        limit: int = 10,
        filter_conditions: Optional[dict] = None,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Semantic search for similar documents.

        Args:
            query: Search query
            limit: Maximum number of results
            filter_conditions: Optional filter (e.g., {"project_id": 1})
            min_score: Minimum similarity score

        Returns:
            List of search results with text and metadata
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Generate query embedding
        query_embedding = await self.embed_text(query)

        # Build filter if provided
        qdrant_filter = None
        if filter_conditions:
            conditions = []
            for key, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            qdrant_filter = Filter(must=conditions)

        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=qdrant_filter,
            score_threshold=min_score,
        )

        # Format results
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"},
            }
            for hit in results
        ]

    async def delete_by_filter(self, filter_conditions: dict) -> int:
        """Delete documents matching filter conditions.

        Args:
            filter_conditions: Filter (e.g., {"document_id": 123})

        Returns:
            Number of deleted documents
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        conditions = []
        for key, value in filter_conditions.items():
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )

        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(must=conditions),
        )

        return result.status

    async def delete_collection(self) -> None:
        """Delete the entire collection."""
        self.client.delete_collection(collection_name=self.collection_name)

    async def get_collection_info(self) -> dict:
        """Get collection statistics.

        Returns:
            Collection information
        """
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status,
            }
        except Exception:
            return {
                "name": self.collection_name,
                "status": "not_found",
            }
