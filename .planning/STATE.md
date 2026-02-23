# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** Extract accurate, citation-backed project summaries and complete requirements checklists from any tender document folder -- turning hours of manual review into minutes.
**Current focus:** Phase 5 in progress -- results interface with four-tab layout (Documents, Summary, Checklist, Search), search tab with hybrid/semantic/keyword modes. Next: 05-03 (Export).

## Current Position

Phase: 5 of 5 (Results Interface & Export)
Plan: 2 of 3 in current phase -- COMPLETE
Status: In progress
Last activity: 2026-02-23 -- Completed 05-02-PLAN.md

Progress: [##################] 93%

## Performance Metrics

**Velocity:**
- Total plans completed: 14 (3 Phase 1 + 3 Phase 2 + 3 Phase 3 + 3 Phase 4 + 2 Phase 5)
- Average duration: ~8.5 min
- Total execution time: ~1 hour 59 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Document Ingestion Pipeline | 3/3 | ~45 min | ~15 min |
| 2. Bilingual Processing & Search | 3/3 | ~33 min | ~11 min |
| 3. Project Summary Extraction | 3/3 | ~18 min | ~6 min |
| 4. Requirements Checklist Extraction | 3/3 | ~17 min | ~6 min |
| 5. Results Interface & Export | 2/3 | ~6 min | ~3 min |

**Recent Trend:**
- Last 5 plans: 04-02, 04-03, 05-01, 05-02
- Trend: Consistent (~2-6 min for recent plans)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Gemini 3 Pro as LLM provider (user preference, cost)
- Local-first deployment, no cloud folders for v1
- Single-user, no auth for v1
- Fresh build using existing bidops-ai/ as reference only
- Docling for PDF parsing (97.9% table accuracy)
- EasyOCR over Tesseract for Arabic OCR
- ChromaDB for local vector storage
- [02-01] PyArabic with regex fallback for Arabic diacritics removal
- [02-01] Script-based pre-check for mixed language detection (Arabic+Latin chars triggers per-section detection)
- [02-01] Conservative bidi correction (only when suspicious number ordering detected)
- [02-02] Tables always emitted as single chunks (never split mid-row)
- [02-02] text_normalized field embedded for consistent query matching; original text in metadata for display
- [02-02] Per-project ChromaDB collections for search isolation
- [02-02] Indexing failures fault-isolated from document parsing (try/except)
- [02-03] alpha=0.7 weights semantic search higher for multilingual queries
- [02-03] BM25 index lazily built on first search, cached with explicit invalidation
- [02-03] Search errors return empty results (graceful degradation, not 500s)
- [03-01] LLMExtractedField separate from ExtractedField -- LLM schema excludes post-processing fields set after NLI verification
- [03-01] Tenacity retry only for network transient errors -- instructor handles validation retries internally
- [03-01] TypeVar T bound to BaseModel for type-safe GeminiService.extract() return type
- [03-02] NLI cross-encoder independent from extraction LLM (avoids self-verification bias)
- [03-02] Lazy NLI model loading to avoid startup delay
- [03-02] Confidence weights: NLI 50%, retrieval 30%, LLM 20%
- [03-02] Lenient NLI threshold (0.3) for keeping citations -- score flows into overall confidence
- [03-03] Per-field extraction with 0.5s inter-field delay to avoid Gemini rate limiting
- [03-03] Individual field failures produce empty ExtractedField (graceful degradation)
- [03-03] Extraction status lifecycle (None -> in_progress -> completed/failed) for concurrency control
- [03-03] Lazy singleton ExtractionService in API layer composes all dependencies on first request
- [04-01] FieldDefinition import moved to TYPE_CHECKING guard to fix pre-existing circular import
- [04-01] Wrapper model (CategoryExtractionResponse) over Iterable for Gemini compatibility
- [04-01] 6 categories with variable max_context_chunks (20 for major, 15 for smaller categories)
- [04-02] Multi-query retrieval merges results across category queries, deduplicates by chunk_id, sorts by score
- [04-02] NLI verification per requirement using same source-chunk matching logic as CitationVerifier._find_source_chunk
- [04-02] Semantic deduplication at 0.9 cosine similarity threshold removes lower-confidence duplicate
- [04-02] Embedding model accessed lazily via search_service._embedding_service._get_model() (no new DI parameter)
- [04-03] Separate service instances for checklist API (not shared with extraction API) for isolation
- [04-03] Database must be recreated for new columns (SQLite create_all only adds new tables, not new columns)
- [05-01] Lazy tab loading: data only fetched when tab first clicked, avoiding unnecessary API calls
- [05-01] Optimistic checkbox toggle: UI updates immediately, reverts on PATCH failure for responsive UX
- [05-01] Category validation in PATCH endpoint rejects invalid category names with 400 error
- [05-02] Search tab uses user-initiated fetch (button/Enter), not lazy-load or on-type, since it starts empty
- [05-02] Search form split into two rows: input+button top, mode selector+count bottom

### Pending Todos

None.

### Blockers/Concerns

- Gemini API key (BIDOPS_GEMINI_API_KEY) must be configured before running extraction pipeline
- Real Arabic tender documents needed for end-to-end validation
- Lingua mixed detection edge case: very lopsided content (1 Arabic word among many English) may classify as dominant language rather than "mixed"
- Existing database file was cleared during 04-03; will be recreated on next server startup with all columns

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 05-02-PLAN.md (Search tab with query form, mode selector, result cards). Next: 05-03 (Export).
Resume file: None
