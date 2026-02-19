---
phase: 02-bilingual-processing-search
plan: 02
subsystem: indexing
tags: [chunking, chromadb, sentence-transformers, embeddings, multilingual, vector-search, semantic-splitting]

# Dependency graph
requires:
  - phase: 01-document-ingestion-pipeline
    provides: "ParsedDocument with PageContent (text + tables per page)"
  - phase: 02-bilingual-processing-search
    plan: 01
    provides: "normalize_for_search and detect_language from text_processing package"
provides:
  - "ChunkingService: semantic document chunking with Arabic-aware separators (~400 char chunks)"
  - "DocumentChunk dataclass with full citation metadata (document_id, page_number, language, char offsets)"
  - "EmbeddingService: per-project ChromaDB collections with multilingual embeddings (paraphrase-multilingual-mpnet-base-v2)"
  - "Auto-indexing integration in document_service.py (chunk + embed after parse)"
  - "Config settings: chroma_persist_dir, embedding_model, chunk_max_chars, chunk_overlap_chars"
affects:
  - "02-03 (search service queries ChromaDB collections created here)"
  - "03-xx (LLM extraction pipeline may use chunked/embedded content for retrieval)"

# Tech tracking
tech-stack:
  added:
    - "chromadb (local persistent vector database with HNSW index)"
    - "sentence-transformers (multilingual embedding model loading and inference)"
  patterns:
    - "Lazy-initialized module singletons for ChunkingService and EmbeddingService"
    - "Recursive character splitting with ordered separator preference"
    - "upsert() for idempotent chunk indexing (handles re-upload without duplicates)"
    - "delete-before-reindex pattern to prevent orphan chunks"
    - "asyncio.to_thread() for CPU-bound embedding in async context"
    - "try/except isolation: indexing failures don't fail document parsing"

key-files:
  created:
    - "app/services/indexing/__init__.py"
    - "app/services/indexing/chunking_service.py"
    - "app/services/indexing/embedding_service.py"
  modified:
    - "app/services/document_service.py"
    - "app/config.py"
    - "requirements.txt"

key-decisions:
  - "Tables always emitted as single chunks regardless of size (never split mid-row)"
  - "Overlap of 50 chars between consecutive text chunks for context continuity"
  - "text_normalized field embedded (not raw text) for consistent search matching"
  - "Original text stored in ChromaDB metadata for display to users"
  - "Per-project ChromaDB collections for isolation and easy project deletion"
  - "Cosine similarity for HNSW space (best for multilingual embeddings)"

patterns-established:
  - "delete_document_chunks() before index_chunks() on re-upload"
  - "upsert() instead of add() for idempotent indexing"
  - "Indexing wrapped in try/except so failures don't block document ingestion"
  - "Lazy singleton pattern for heavy services (_get_chunking_service, _get_embedding_service)"

requirements-completed: [SRH-02]

# Metrics
duration: 10min
completed: 2026-02-19
---

# Phase 2 Plan 2: Semantic Document Chunking and ChromaDB Vector Indexing Summary

**Recursive semantic chunking with Arabic-aware separators, ChromaDB per-project vector collections using paraphrase-multilingual-mpnet-base-v2, and auto-indexing integration in document processing pipeline**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-02-19
- **Completed:** 2026-02-19
- **Tasks:** 2/2
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments
- ChunkingService splits documents at semantic boundaries (paragraphs, sentences, Arabic commas) into ~400-char chunks with 50-char overlap
- Tables are always kept as single chunks -- never split mid-row regardless of table size
- Each DocumentChunk carries full citation metadata: document_id, page_number, language, section_name, char_start, char_end
- EmbeddingService manages per-project ChromaDB collections with cosine similarity HNSW index
- document_service.py auto-indexes documents after successful parsing with fault-isolated try/except
- Indexing uses upsert() for idempotency and delete-before-reindex for clean re-uploads

## Task Commits

Each task was committed atomically:

1. **Task 1: Create chunking service and embedding service with ChromaDB** - `532feb9` (feat)
2. **Task 2: Integrate chunking and indexing into document processing pipeline** - `b18c7a9` (feat)

## Files Created/Modified
- `app/services/indexing/__init__.py` - Package init with re-exports for ChunkingService, DocumentChunk, EmbeddingService
- `app/services/indexing/chunking_service.py` - Recursive semantic chunking with Arabic-aware separators, table-as-one-chunk, section heading detection
- `app/services/indexing/embedding_service.py` - ChromaDB PersistentClient wrapper with lazy init, per-project collections, upsert/delete operations
- `app/services/document_service.py` - Added lazy-init indexing services and post-parse chunking/indexing integration
- `app/config.py` - Added chroma_persist_dir, embedding_model, chunk_max_chars, chunk_overlap_chars settings
- `requirements.txt` - Added chromadb and sentence-transformers

## Decisions Made
- **Tables as single chunks:** Tables are never split regardless of size. A 1600+ char table is still one chunk. This preserves table structure for citation and avoids mid-row splits that would produce meaningless fragments.
- **text_normalized for embedding:** The normalized text (lowercase, Arabic-normalized) is what gets embedded and stored as the ChromaDB document. The original text is stored in metadata for display. This ensures query-time normalization matches index-time normalization.
- **Per-project collections:** Each project gets its own ChromaDB collection (project_{id}). This provides natural isolation for search scope and enables atomic project deletion without scanning all chunks.
- **Fault-isolated indexing:** The indexing try/except block in document_service.py means a ChromaDB crash, model download failure, or embedding error will NOT prevent the document from being marked as COMPLETED. Users can still view parsed text even if search is temporarily broken.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - chromadb and sentence-transformers install via pip from requirements.txt. The embedding model (~420MB) downloads automatically on first use and is cached by sentence-transformers.

## Next Phase Readiness
- ChromaDB collections ready for querying by search service (Plan 02-03)
- EmbeddingService.get_collection() returns configured collection for search queries
- DocumentChunk metadata structure matches what search service will need for result formatting
- No blockers for Plan 02-03 (hybrid search API with BM25 + vector similarity)

---
*Phase: 02-bilingual-processing-search*
*Plan: 02*
*Completed: 2026-02-19*
