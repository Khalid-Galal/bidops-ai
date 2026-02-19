---
phase: 03-project-summary-extraction
plan: 03
subsystem: extraction
tags: [extraction-pipeline, per-field-retrieval, gemini, nli, citation-verification, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 03-project-summary-extraction
    plan: 01
    provides: "GeminiService, Pydantic extraction schemas, field definitions, context builder"
  - phase: 03-project-summary-extraction
    plan: 02
    provides: "CitationVerifier with NLI cross-encoder and confidence scoring"
  - phase: 02-bilingual-processing-search
    provides: "HybridSearchService with SearchResult for per-field retrieval"
provides:
  - "ExtractionService orchestrating per-field retrieval, LLM extraction, and NLI verification"
  - "POST /api/projects/{project_id}/extract endpoint for triggering extraction"
  - "GET /api/projects/{project_id}/extract endpoint for retrieving stored results"
  - "Project model with summary_json and extraction_status persistence"
affects:
  - 04-requirements-checklist (reuses extraction pipeline pattern)
  - 05-results-interface-export (reads ProjectSummary from summary_json)

# Tech tracking
tech-stack:
  added: []
  patterns: [per-field-retrieval-then-extract, lazy-singleton-service, extraction-status-lifecycle]

key-files:
  created:
    - app/services/extraction/extraction_service.py
    - app/api/extraction.py
  modified:
    - app/models/project.py
    - app/services/extraction/__init__.py
    - app/main.py

key-decisions:
  - "Per-field extraction with 0.5s inter-field delay to avoid Gemini rate limiting"
  - "Individual field failures produce empty ExtractedField rather than crashing entire extraction"
  - "Extraction status lifecycle (None -> in_progress -> completed/failed) prevents duplicate concurrent extractions"
  - "Lazy singleton ExtractionService in API layer follows same pattern as search API"

patterns-established:
  - "Per-field retrieval: each of 13 fields gets its own hybrid search query, context build, LLM call, and NLI verify"
  - "Extraction status lifecycle: database column tracks extraction state for concurrency control"
  - "Lazy service composition: API layer composes all services (embedding, search, LLM, verifier, extraction) on first request"

requirements-completed: [SUM-01, SUM-02, SUM-03, SUM-04, SUM-05, SUM-06, CIT-01, CIT-02, CIT-03, CIT-04]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 3 Plan 03: Extraction Pipeline Summary

**ExtractionService orchestrates per-field hybrid retrieval, Gemini extraction, and NLI citation verification across all 13 project summary fields, exposed via REST API with database persistence and status tracking**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T10:06:37Z
- **Completed:** 2026-02-19T10:11:48Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- ExtractionService orchestrates the full pipeline: for each of 13 fields, retrieves chunks via hybrid search, builds labeled context, extracts via Gemini LLM, verifies citations via NLI cross-encoder, and stores verified results
- POST endpoint triggers extraction and persists ProjectSummary JSON to database; GET endpoint returns stored results without re-extraction
- Extraction status lifecycle (None -> in_progress -> completed/failed) prevents duplicate concurrent extractions (409 Conflict)
- Individual field extraction failures are gracefully handled -- empty ExtractedField created, pipeline continues to remaining fields
- Gemini API key validated at service initialization with clear error message

## Task Commits

Each task was committed atomically:

1. **Task 1: Add summary storage columns to Project model and create ExtractionService** - `253de69` (feat)
2. **Task 2: Create extraction API endpoint and register router** - `10bae16` (feat)

## Files Created/Modified
- `app/services/extraction/extraction_service.py` - ExtractionService with extract_project_summary() and extract_and_persist() methods
- `app/api/extraction.py` - POST and GET /api/projects/{project_id}/extract endpoints with lazy singleton service
- `app/models/project.py` - Added summary_json (Text) and extraction_status (String) columns
- `app/services/extraction/__init__.py` - Re-exports ExtractionService and CitationVerifier
- `app/main.py` - Registered extraction_router with /api prefix

## Decisions Made
- Per-field extraction uses 0.5s delay between Gemini API calls to avoid rate limiting (conservative, can be reduced)
- Individual field failures produce empty ExtractedField (value=None, confidence=0.0, requires_review=True) rather than aborting the entire extraction -- graceful degradation
- Extraction status tracked in database column for concurrency control (409 Conflict when in_progress)
- Lazy singleton pattern for ExtractionService in API layer composes all dependencies on first request -- same pattern as search API

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**External services require manual configuration.** The Gemini API key must be set before using the extraction pipeline:
- Set `BIDOPS_GEMINI_API_KEY` environment variable with a key from [Google AI Studio](https://aistudio.google.com/apikey)
- Or add `BIDOPS_GEMINI_API_KEY=your_key_here` to `.env` file

## Next Phase Readiness
- Phase 3 complete -- all 13 summary fields extractable with citation-backed, confidence-scored results
- Phase 4 (Requirements Checklist) can reuse the per-field extraction pipeline pattern
- Phase 5 (Results Interface) can read ProjectSummary from project.summary_json
- Real Arabic tender documents needed for end-to-end validation with Gemini API key

---
*Phase: 03-project-summary-extraction*
*Completed: 2026-02-19*
