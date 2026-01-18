"""Document processing and ingestion service."""

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_context
from app.models import Document, DocumentChunk, Project
from app.models.base import DocumentCategory, DocumentStatus
from app.parsers.base import ParserRegistry, ParsedContent
from app.services.vector_store import VectorStoreService

settings = get_settings()


class DocumentService:
    """Service for document processing and ingestion.

    Handles:
    - File discovery and hashing
    - Document parsing
    - Text chunking
    - Embedding generation
    - Database and vector store updates
    """

    def __init__(self):
        """Initialize document service."""
        self.vector_store = VectorStoreService()
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP

    async def ingest_project_folder(
        self,
        project_id: int,
        folder_path: Optional[str] = None,
        force_reindex: bool = False,
        callback: Optional[callable] = None,
    ) -> dict:
        """Ingest all documents from a project folder.

        Args:
            project_id: Project ID
            folder_path: Folder path (uses project path if not provided)
            force_reindex: Reprocess already indexed documents
            callback: Optional progress callback function

        Returns:
            Ingestion summary statistics
        """
        async with get_db_context() as db:
            # Get project
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            folder = Path(folder_path or project.folder_path)
            if not folder.exists():
                raise ValueError(f"Folder not found: {folder}")

            # Discover files
            files = self._discover_files(folder)

            stats = {
                "total_files": len(files),
                "processed": 0,
                "indexed": 0,
                "skipped": 0,
                "failed": 0,
                "errors": [],
            }

            # Update project
            project.total_documents = len(files)
            project.status = "ingesting"
            await db.commit()

            # Process each file
            for i, file_path in enumerate(files):
                try:
                    result = await self._process_file(
                        db, project_id, file_path, force_reindex
                    )

                    if result == "indexed":
                        stats["indexed"] += 1
                    elif result == "skipped":
                        stats["skipped"] += 1
                    else:
                        stats["failed"] += 1

                    stats["processed"] += 1

                    # Progress callback
                    if callback:
                        await callback({
                            "current": i + 1,
                            "total": len(files),
                            "file": file_path.name,
                            "status": result,
                        })

                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({
                        "file": str(file_path),
                        "error": str(e),
                    })

            # Update project stats
            project.indexed_documents = stats["indexed"]
            project.failed_documents = stats["failed"]
            project.status = "ready"
            await db.commit()

            return stats

    def _discover_files(self, folder: Path) -> list[Path]:
        """Discover all supported files in a folder.

        Args:
            folder: Folder to scan

        Returns:
            List of file paths
        """
        supported_extensions = set(ParserRegistry.get_supported_extensions())
        files = []

        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                file_path = Path(root) / filename
                if file_path.suffix.lower() in supported_extensions:
                    files.append(file_path)

        return sorted(files)

    async def _process_file(
        self,
        db: AsyncSession,
        project_id: int,
        file_path: Path,
        force_reindex: bool,
    ) -> str:
        """Process a single file.

        Args:
            db: Database session
            project_id: Project ID
            file_path: File path
            force_reindex: Force reprocessing

        Returns:
            Status string: "indexed", "skipped", or "failed"
        """
        # Calculate file hash
        content_hash = self._calculate_hash(file_path)

        # Check if already indexed
        if not force_reindex:
            result = await db.execute(
                select(Document).where(
                    Document.project_id == project_id,
                    Document.content_hash == content_hash,
                    Document.status == DocumentStatus.INDEXED,
                )
            )
            if result.scalar_one_or_none():
                return "skipped"

        # Get parser
        parser = ParserRegistry.get_parser(str(file_path))
        if not parser:
            return "failed"

        try:
            # Parse document
            parsed = await parser.parse(str(file_path))

            if not parsed.has_content:
                return "failed"

            # Create or update document record
            result = await db.execute(
                select(Document).where(
                    Document.project_id == project_id,
                    Document.file_path == str(file_path),
                )
            )
            document = result.scalar_one_or_none()

            if document:
                # Update existing
                document.content_hash = content_hash
                document.extracted_text = parsed.text
                document.page_count = parsed.page_count
                document.metadata = parsed.metadata
                document.status = DocumentStatus.INDEXED
                document.processing_time_ms = parsed.processing_time_ms
                document.indexed_at = datetime.now(timezone.utc)
            else:
                # Create new
                document = Document(
                    project_id=project_id,
                    filename=file_path.name,
                    file_path=str(file_path),
                    file_type=file_path.suffix.lower().lstrip("."),
                    file_size=file_path.stat().st_size,
                    content_hash=content_hash,
                    extracted_text=parsed.text,
                    page_count=parsed.page_count,
                    metadata=parsed.metadata,
                    status=DocumentStatus.INDEXED,
                    processing_time_ms=parsed.processing_time_ms,
                    indexed_at=datetime.now(timezone.utc),
                )
                db.add(document)

            await db.flush()

            # Classify document category
            document.category = await self._classify_document(parsed)

            # Detect language
            document.language = self._detect_language(parsed.text)

            # Chunk and embed
            await self._chunk_and_embed(db, document, parsed)

            await db.commit()
            return "indexed"

        except Exception as e:
            # Mark as failed
            result = await db.execute(
                select(Document).where(
                    Document.project_id == project_id,
                    Document.file_path == str(file_path),
                )
            )
            document = result.scalar_one_or_none()

            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = str(e)
                await db.commit()

            raise

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file.

        Args:
            file_path: File path

        Returns:
            Hex digest of hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _classify_document(self, parsed: ParsedContent) -> DocumentCategory:
        """Classify document into a category.

        Args:
            parsed: Parsed document content

        Returns:
            Document category
        """
        text_lower = parsed.text.lower()[:5000]  # First 5000 chars

        # Simple keyword-based classification
        if any(kw in text_lower for kw in ["invitation to tender", "itt", "request for proposal", "rfp"]):
            return DocumentCategory.ITT
        elif any(kw in text_lower for kw in ["specification", "technical requirement", "spec"]):
            return DocumentCategory.SPECS
        elif any(kw in text_lower for kw in ["bill of quantities", "boq", "schedule of rates"]):
            return DocumentCategory.BOQ
        elif any(kw in text_lower for kw in ["drawing", "dwg", "elevation", "section", "plan"]):
            return DocumentCategory.DRAWINGS
        elif any(kw in text_lower for kw in ["contract", "agreement", "terms and conditions"]):
            return DocumentCategory.CONTRACT
        elif any(kw in text_lower for kw in ["addendum", "amendment", "revision"]):
            return DocumentCategory.ADDENDUM
        elif any(kw in text_lower for kw in ["health", "safety", "environment", "hse"]):
            return DocumentCategory.HSE
        elif any(kw in text_lower for kw in ["schedule", "programme", "milestone", "gantt"]):
            return DocumentCategory.SCHEDULE

        return DocumentCategory.GENERAL

    def _detect_language(self, text: str) -> str:
        """Detect text language.

        Args:
            text: Text content

        Returns:
            Language code (en, ar, etc.)
        """
        # Simple Arabic detection based on character ranges
        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        latin_chars = sum(1 for c in text if "a" <= c.lower() <= "z")

        if arabic_chars > latin_chars:
            return "ar"
        return "en"

    async def _chunk_and_embed(
        self,
        db: AsyncSession,
        document: Document,
        parsed: ParsedContent,
    ) -> None:
        """Chunk text and create embeddings.

        Args:
            db: Database session
            document: Document record
            parsed: Parsed content
        """
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        # Delete existing chunks
        await db.execute(
            DocumentChunk.__table__.delete().where(
                DocumentChunk.document_id == document.id
            )
        )

        # Delete existing vectors
        await self.vector_store.delete_by_filter({"document_id": document.id})

        # Split text into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        chunks = splitter.split_text(parsed.text)

        if not chunks:
            return

        # Create chunk records and embeddings
        chunk_texts = []
        chunk_metadatas = []
        chunk_records = []

        char_pos = 0
        for i, chunk_text in enumerate(chunks):
            # Find chunk position in original text
            chunk_start = parsed.text.find(chunk_text, char_pos)
            if chunk_start == -1:
                chunk_start = char_pos
            chunk_end = chunk_start + len(chunk_text)
            char_pos = chunk_end

            # Determine page number if pages available
            page_num = None
            if parsed.pages:
                cumulative_length = 0
                for page_idx, page_text in enumerate(parsed.pages):
                    cumulative_length += len(page_text)
                    if cumulative_length >= chunk_start:
                        page_num = page_idx + 1
                        break

            # Create chunk record
            chunk_record = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                chunk_text=chunk_text,
                char_start=chunk_start,
                char_end=chunk_end,
                page_number=page_num,
            )
            chunk_records.append(chunk_record)

            chunk_texts.append(chunk_text)
            chunk_metadatas.append({
                "document_id": document.id,
                "project_id": document.project_id,
                "filename": document.filename,
                "chunk_index": i,
                "page_number": page_num,
                "category": document.category.value if document.category else None,
            })

        # Add chunks to database
        db.add_all(chunk_records)
        await db.flush()

        # Add to vector store
        vector_ids = await self.vector_store.add_documents(
            texts=chunk_texts,
            metadatas=chunk_metadatas,
        )

        # Update chunk records with vector IDs
        for chunk_record, vector_id in zip(chunk_records, vector_ids):
            chunk_record.vector_id = vector_id

        # Store vector IDs in document
        document.vector_ids = vector_ids

    async def search_documents(
        self,
        query: str,
        project_id: Optional[int] = None,
        categories: Optional[list[DocumentCategory]] = None,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Semantic search across documents.

        Args:
            query: Search query
            project_id: Optional project filter
            categories: Optional category filter
            limit: Maximum results
            min_score: Minimum similarity score

        Returns:
            List of search results
        """
        filter_conditions = {}

        if project_id:
            filter_conditions["project_id"] = project_id

        if categories:
            # Note: Qdrant doesn't support OR in filters easily,
            # so we'd need multiple queries or a different approach
            pass

        results = await self.vector_store.search(
            query=query,
            limit=limit,
            filter_conditions=filter_conditions if filter_conditions else None,
            min_score=min_score,
        )

        return results

    async def get_document_content(
        self,
        document_id: int,
    ) -> Optional[dict]:
        """Get full document content.

        Args:
            document_id: Document ID

        Returns:
            Document content and metadata
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()

            if not document:
                return None

            return {
                "id": document.id,
                "filename": document.filename,
                "text": document.extracted_text,
                "metadata": document.metadata,
                "page_count": document.page_count,
                "category": document.category.value if document.category else None,
                "language": document.language,
            }
