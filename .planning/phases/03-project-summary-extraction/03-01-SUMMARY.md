---
phase: 03-project-summary-extraction
plan: 01
subsystem: extraction
tags: [gemini, instructor, pydantic, llm, structured-output, tenacity]

# Dependency graph
requires:
  - phase: 02-bilingual-processing-search
    provides: "HybridSearchService with SearchResult dataclass for per-field retrieval"
provides:
  - "GeminiService for instructor-wrapped structured LLM extraction"
  - "Pydantic extraction schemas (Citation, ExtractedField, LLMExtractedField, ProjectSummary, ExtractionResponse)"
  - "13 FieldDefinition entries in SUMMARY_FIELDS with query hints for per-field retrieval"
  - "Context builder for labeled chunk assembly with [SOURCE:... | PAGE:...] labels"
  - "Config settings for Gemini API key, model, NLI model, and confidence thresholds"
affects:
  - 03-02 (NLI citation verification uses ExtractedField and confidence thresholds)
  - 03-03 (Extraction pipeline orchestrates GeminiService, context builder, and field definitions)

# Tech tracking
tech-stack:
  added: [google-genai, instructor, tenacity]
  patterns: [instructor.from_provider for structured LLM output, lazy client initialization, labeled context assembly, per-field extraction schemas]

key-files:
  created:
    - app/schemas/extraction.py
    - app/services/extraction/__init__.py
    - app/services/extraction/field_definitions.py
    - app/services/llm/__init__.py
    - app/services/llm/gemini_service.py
    - app/services/llm/context_builder.py
  modified:
    - app/config.py
    - requirements.txt

key-decisions:
  - "LLMExtractedField separate from ExtractedField -- LLM schema excludes post-processing fields (confidence_level, requires_review) that are set after NLI verification"
  - "Tenacity retry only for network transient errors (ConnectionError, TimeoutError) -- instructor handles validation retries internally"
  - "TypeVar T bound to BaseModel for type-safe extract() return type"

patterns-established:
  - "Lazy client initialization: GeminiService._get_client() initializes instructor client on first use"
  - "Labeled context: [SOURCE:filename | PAGE:N] prefix on each chunk for LLM citation attribution"
  - "Field-specific prompts: build_extraction_prompt() adds type-specific instructions (date preservation, list formatting)"

requirements-completed: [SUM-01, SUM-02, SUM-03, SUM-04, SUM-05, SUM-06]

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 3 Plan 01: LLM Service & Extraction Schemas Summary

**Instructor-wrapped GeminiService with Pydantic extraction schemas (Citation, ExtractedField, ProjectSummary), 13 field definitions with query hints, and labeled context builder for per-field retrieval-then-extract**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-19T09:55:23Z
- **Completed:** 2026-02-19T10:02:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Pydantic schemas enforce citation structure (document_name + page_number + quote) on every extracted field
- GeminiService provides structured extraction with instructor retry-on-validation-failure and tenacity retry for network errors
- 13 field definitions drive per-field retrieval from hybrid search with tailored queries and top_k values
- Context builder labels chunks with source metadata for accurate LLM citation attribution
- Config updated with Gemini API key, model, NLI model, and confidence thresholds (all with BIDOPS_ env prefix)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Pydantic extraction schemas, field definitions, and update config** - `7d8431f` (feat)
2. **Task 2: Create GeminiService with instructor and context builder** - `f025388` (feat)

## Files Created/Modified
- `app/schemas/extraction.py` - Citation, LLMExtractedField, ExtractedField, ProjectSummary, ExtractionResponse Pydantic models
- `app/services/extraction/__init__.py` - Package init re-exporting FieldDefinition and SUMMARY_FIELDS
- `app/services/extraction/field_definitions.py` - FieldDefinition dataclass and 13 SUMMARY_FIELDS entries with query hints
- `app/services/llm/__init__.py` - Package init re-exporting GeminiService, build_labeled_context, build_extraction_prompt
- `app/services/llm/gemini_service.py` - Instructor-wrapped Gemini client with lazy init and tenacity retry
- `app/services/llm/context_builder.py` - build_labeled_context() and build_extraction_prompt() for chunk formatting
- `app/config.py` - Added gemini_api_key, gemini_model, nli_model, confidence thresholds to Settings
- `requirements.txt` - Added google-genai, instructor, tenacity

## Decisions Made
- LLMExtractedField created as separate schema from ExtractedField -- the LLM only fills value, confidence, citations, reasoning; confidence_level and requires_review are computed post-extraction after NLI verification
- Tenacity retry decorator placed on extract() for network transient errors only (ConnectionError, TimeoutError) -- instructor already handles validation retries internally via max_retries parameter
- Used TypeVar T bound to BaseModel for type-safe extract() method return type

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed Phase 3 dependencies**
- **Found during:** Task 2 verification (LLM imports)
- **Issue:** google-genai, instructor, tenacity not installed -- imports failed with ModuleNotFoundError
- **Fix:** Ran `pip install google-genai instructor tenacity`
- **Files modified:** None (runtime only)
- **Verification:** All imports succeed after installation
- **Committed in:** N/A (pip install, not a code change)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to verify imports. No scope creep.

## Issues Encountered
None -- plan executed as written after dependency installation.

## User Setup Required

**External services require manual configuration.** The Gemini API key must be set before Phase 3 Plan 03 (extraction pipeline):
- Set `BIDOPS_GEMINI_API_KEY` environment variable with a key from [Google AI Studio](https://aistudio.google.com/apikey)
- Or add `BIDOPS_GEMINI_API_KEY=your_key_here` to `.env` file

## Next Phase Readiness
- GeminiService, extraction schemas, field definitions, and context builder ready for 03-02 (NLI citation verification)
- 03-02 will use ExtractedField schema and confidence thresholds from config
- 03-03 will orchestrate GeminiService + context builder + field definitions into the full extraction pipeline
- Gemini API key not yet needed -- only required when extraction pipeline runs in 03-03

---
*Phase: 03-project-summary-extraction*
*Completed: 2026-02-19*
