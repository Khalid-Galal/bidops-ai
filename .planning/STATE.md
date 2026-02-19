# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** Extract accurate, citation-backed project summaries and complete requirements checklists from any tender document folder -- turning hours of manual review into minutes.
**Current focus:** Phase 3 in progress -- LLM service, extraction schemas, and NLI citation verification complete, extraction pipeline orchestration next

## Current Position

Phase: 3 of 5 (Project Summary Extraction)
Plan: 2 of 3 in current phase
Status: In progress
Last activity: 2026-02-19 -- Completed 03-02-PLAN.md

Progress: [########..] 53%

## Performance Metrics

**Velocity:**
- Total plans completed: 8 (3 Phase 1 + 3 Phase 2 + 2 Phase 3)
- Average duration: ~12 min
- Total execution time: ~1 hour 31 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Document Ingestion Pipeline | 3/3 | ~45 min | ~15 min |
| 2. Bilingual Processing & Search | 3/3 | ~33 min | ~11 min |
| 3. Project Summary Extraction | 2/3 | ~13 min | ~7 min |

**Recent Trend:**
- Last 5 plans: 02-01, 02-02, 02-03, 03-01, 03-02
- Trend: Accelerating (~6 min for 03-02)

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

### Pending Todos

None.

### Blockers/Concerns

- Gemini API key (BIDOPS_GEMINI_API_KEY) must be configured before running extraction pipeline in 03-03
- Real Arabic tender documents needed for validation
- Lingua mixed detection edge case: very lopsided content (1 Arabic word among many English) may classify as dominant language rather than "mixed"

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 03-02-PLAN.md (NLI citation verification with cross-encoder and confidence scoring). Next: 03-03 (extraction pipeline orchestration).
Resume file: None
