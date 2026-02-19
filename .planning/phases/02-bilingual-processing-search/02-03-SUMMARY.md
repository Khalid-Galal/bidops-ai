---
phase: 02-bilingual-processing-search
plan: 03
subsystem: search
tags: [bm25, chromadb, hybrid-search, rrf, reciprocal-rank-fusion, keyword-search, semantic-search, fastapi]

# Dependency graph
requires:
  - phase: 02-bilingual-processing-search
    plan: 01
    provides: "normalize_for_search and detect_language from text_processing package"
  - phase: 02-bilingual-processing-search
    plan: 02
    provides: "EmbeddingService with per-project ChromaDB collections and DocumentChunk metadata"
provides:
  - "KeywordSearchService: BM25Okapi keyword search with lazy index building and cache invalidation"
  - "VectorSearchService: ChromaDB semantic similarity search with query normalization"
  - "HybridSearchService: RRF fusion of keyword + semantic with configurable alpha/rrf_k"
  - "SearchResult dataclass with full citation metadata (document_id, page_number, filename, language)"
  - "GET /api/projects/{project_id}/search endpoint with hybrid/semantic/keyword modes"
  - "SearchResponse and SearchResultItem Pydantic schemas for API serialization"
affects:
  - "03-xx (LLM extraction pipeline may use search for retrieval-augmented generation)"
  - "04-xx (UI will consume search API endpoint for document search interface)"

# Tech tracking
tech-stack:
  added:
    - "rank-bm25 (BM25Okapi keyword search implementation)"
  patterns:
    - "Lazy singleton for HybridSearchService (same pattern as document_service)"
    - "Reciprocal Rank Fusion (RRF) for multi-signal result merging"
    - "BM25 index cache with explicit invalidation on new document indexing"
    - "Over-retrieval (top_k * 3) before fusion for better recall"
    - "Graceful empty results on missing/empty collections (no 500 errors)"

key-files:
  created:
    - "app/services/search/__init__.py"
    - "app/services/search/vector_search.py"
    - "app/services/search/keyword_search.py"
    - "app/services/search/hybrid_search.py"
    - "app/schemas/search.py"
    - "app/api/search.py"
  modified:
    - "app/main.py"
    - "requirements.txt"

key-decisions:
  - "alpha=0.7 weights semantic search higher than keyword (better for multilingual queries)"
  - "rrf_k=60 standard constant from original RRF paper"
  - "BM25 index lazily built on first search, cached per project with explicit invalidation"
  - "Over-retrieve top_k*3 results before RRF fusion for better recall"
  - "BM25 scores normalized to 0-1 range for keyword-only mode display consistency"
  - "Search errors return empty results instead of 500 errors (graceful degradation)"

patterns-established:
  - "Lazy singleton _get_search_service() in API module for heavy service initialization"
  - "normalize_for_search() applied to both indexed text and queries for consistent matching"
  - "invalidate_keyword_index() must be called after new documents are indexed"
  - "ChromaDB distance converted to similarity (1 - distance) for semantic-only results"

requirements-completed: [SRH-01, SRH-02]

# Metrics
duration: 8min
completed: 2026-02-19
---

# Phase 2 Plan 3: Hybrid Search API with BM25 Keyword + ChromaDB Semantic + RRF Fusion Summary

**BM25 keyword search, ChromaDB vector similarity, and Reciprocal Rank Fusion hybrid search exposed via GET /api/projects/{project_id}/search with three modes (hybrid/semantic/keyword)**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-02-19
- **Completed:** 2026-02-19
- **Tasks:** 2/2
- **Files modified:** 8 (6 created, 2 modified)

## Accomplishments
- KeywordSearchService provides BM25Okapi keyword search with lazy index building from ChromaDB collections and cache invalidation for fresh data after new document indexing
- VectorSearchService wraps ChromaDB semantic similarity queries with the same normalize_for_search() applied at indexing time, ensuring Arabic diacritics/alef normalization consistency
- HybridSearchService fuses both result sets using Reciprocal Rank Fusion (alpha=0.7 semantic, rrf_k=60) with over-retrieval for better recall
- REST API endpoint at GET /api/projects/{project_id}/search accepts q, mode (hybrid/semantic/keyword), and limit parameters with full Pydantic validation
- Empty/missing collections return empty results gracefully -- no 500 errors for projects without indexed documents

## Task Commits

Each task was committed atomically:

1. **Task 1: Create keyword search, vector search, and hybrid search services** - `d9c425e` (feat)
2. **Task 2: Create search API endpoint with Pydantic schemas and register router** - `accdc24` (feat)

## Files Created/Modified
- `app/services/search/__init__.py` - Package init re-exporting KeywordSearchService, VectorSearchService, HybridSearchService, SearchResult
- `app/services/search/vector_search.py` - ChromaDB semantic similarity search with query normalization and language filtering
- `app/services/search/keyword_search.py` - BM25Okapi keyword search with lazy index build, cache per project, invalidation mechanism
- `app/services/search/hybrid_search.py` - RRF fusion combining keyword and semantic results, SearchResult dataclass with citation metadata
- `app/schemas/search.py` - SearchResultItem and SearchResponse Pydantic models for API serialization
- `app/api/search.py` - GET endpoint with lazy HybridSearchService singleton, project validation, error handling
- `app/main.py` - Added search_router registration after documents_router
- `requirements.txt` - Added rank-bm25 dependency

## Decisions Made
- **alpha=0.7 for semantic weight:** Semantic search is weighted higher than keyword because multilingual content benefits more from meaning-based retrieval. Users searching in Arabic can find English content and vice versa. Keyword search (0.3 weight) still contributes for exact term matching.
- **Lazy BM25 index with explicit invalidation:** The BM25 index is built on first search (not at startup or document upload) to avoid unnecessary work. The invalidate_index() method must be called after new documents are indexed -- callers are responsible for triggering this.
- **Over-retrieval before fusion (top_k * 3):** Retrieving 3x the requested results from each search method before RRF fusion ensures that relevant chunks that rank differently in each method still have a chance to surface in the combined results.
- **Graceful empty results:** When a project has no indexed documents or the ChromaDB collection doesn't exist, the search returns an empty result list with total_results=0 rather than raising an error. This is the expected state for new projects before document upload.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - rank-bm25 installs via pip from requirements.txt. No additional configuration needed.

## Next Phase Readiness
- Search infrastructure complete: all three search modes (hybrid, keyword, semantic) operational
- Phase 2 is now fully complete (all 3 plans: text processing, indexing, search)
- Ready for Phase 3 (LLM extraction pipeline) which can use search for retrieval-augmented generation
- The search endpoint returns document_id, page_number, and filename with each result for citation linking in the UI (Phase 4)
- No blockers for subsequent phases

---
*Phase: 02-bilingual-processing-search*
*Plan: 03*
*Completed: 2026-02-19*
