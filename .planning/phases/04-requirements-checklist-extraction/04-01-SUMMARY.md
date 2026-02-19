---
phase: 04-requirements-checklist-extraction
plan: 01
subsystem: extraction
tags: [pydantic, dataclass, checklist, requirements, categories, prompt-builder]

# Dependency graph
requires:
  - phase: 03-project-summary-extraction
    provides: Citation schema, context_builder, GeminiService, CitationVerifier
provides:
  - RequirementItem, CategoryExtractionResponse, VerifiedRequirement, RequirementsChecklist, ChecklistResponse schemas
  - CategoryDefinition dataclass with 6 category entries
  - build_checklist_extraction_prompt() function
affects: [04-02 checklist service, 04-03 checklist API]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Category-based extraction definitions (CategoryDefinition dataclass)"
    - "Wrapper model pattern for instructor list extraction (CategoryExtractionResponse)"
    - "TYPE_CHECKING guard for cross-package imports to avoid circular imports"

key-files:
  created:
    - app/schemas/checklist.py
    - app/services/extraction/checklist_definitions.py
  modified:
    - app/services/llm/context_builder.py

key-decisions:
  - "[04-01] FieldDefinition import moved to TYPE_CHECKING guard to fix pre-existing circular import"
  - "[04-01] Wrapper model (CategoryExtractionResponse) over Iterable for Gemini compatibility"
  - "[04-01] 6 categories with variable max_context_chunks (20 for major, 15 for smaller categories)"

patterns-established:
  - "CategoryDefinition dataclass: name, display_name, description, queries, top_k_per_query, max_context_chunks, prompt_hints"
  - "build_checklist_extraction_prompt(): category-focused prompt with skip-list for other categories"

requirements-completed: [CHK-05]

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 4 Plan 1: Schemas, Category Definitions, and Prompt Builder Summary

**Pydantic checklist schemas (5 models), 6 CategoryDefinition entries with multi-query retrieval params, and checklist-specific prompt builder added to context_builder**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-19T10:53:29Z
- **Completed:** 2026-02-19T11:00:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Five Pydantic models for the full checklist extraction pipeline: RequirementItem (LLM schema), CategoryExtractionResponse (wrapper), VerifiedRequirement (post-NLI), RequirementsChecklist (assembled), ChecklistResponse (API)
- Six CategoryDefinition entries (technical, commercial, legal, hse, submission_documents, eligibility) with 3 queries each, variable chunk limits, and category-specific prompt hints
- build_checklist_extraction_prompt() function that generates category-focused extraction prompts with mandatory classification guidance and explicit skip-lists for other categories

## Task Commits

Each task was committed atomically:

1. **Task 1: Create checklist Pydantic schemas** - `6afc458` (feat)
2. **Task 2: Create category definitions and extend context_builder** - `ec00393` (feat)

## Files Created/Modified
- `app/schemas/checklist.py` - 5 Pydantic models for checklist extraction pipeline (RequirementItem, CategoryExtractionResponse, VerifiedRequirement, RequirementsChecklist, ChecklistResponse)
- `app/services/extraction/checklist_definitions.py` - CategoryDefinition dataclass and CHECKLIST_CATEGORIES list with 6 entries
- `app/services/llm/context_builder.py` - Added build_checklist_extraction_prompt(), moved FieldDefinition to TYPE_CHECKING guard

## Decisions Made
- Moved FieldDefinition import in context_builder.py into TYPE_CHECKING guard to fix pre-existing circular import (context_builder -> field_definitions -> extraction __init__ -> extraction_service -> context_builder)
- Used wrapper model pattern (CategoryExtractionResponse) instead of Iterable for Gemini structured output compatibility as recommended by research

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing circular import in context_builder.py**
- **Found during:** Task 2 (extending context_builder)
- **Issue:** `from app.services.extraction.field_definitions import FieldDefinition` at module level caused circular import when context_builder was the entry point (context_builder -> extraction __init__ -> extraction_service -> context_builder)
- **Fix:** Moved FieldDefinition import into TYPE_CHECKING guard; `from __future__ import annotations` ensures type hints work as strings at runtime
- **Files modified:** app/services/llm/context_builder.py
- **Verification:** All three context_builder functions import correctly; ExtractionService still works
- **Committed in:** ec00393 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Pre-existing circular import fixed to enable new function addition. No scope creep.

## Issues Encountered
None beyond the circular import fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Schemas ready for checklist_service.py (Plan 02) to orchestrate category-based extraction
- CategoryDefinition and build_checklist_extraction_prompt() ready for multi-query retrieval and LLM extraction
- All imports verified, no circular dependencies

---
*Phase: 04-requirements-checklist-extraction*
*Completed: 2026-02-19*
