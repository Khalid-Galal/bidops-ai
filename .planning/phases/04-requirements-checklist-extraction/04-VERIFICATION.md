---
phase: 04-requirements-checklist-extraction
verified: 2026-02-19T00:00:00Z
status: passed
score: 18/18 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Trigger POST /api/projects/{id}/checklist with a real project that has indexed documents"
    expected: "Checklist extraction runs all 6 categories, persists results, returns ChecklistResponse with status=completed and non-empty checklist"
    why_human: "Requires a running server, real Gemini API key, and indexed documents; cannot verify extraction quality programmatically"
  - test: "Check that requirements are correctly categorized (technical vs commercial vs legal vs HSE)"
    expected: "Requirements appear in the correct category group; no cross-category contamination visible in the returned checklist"
    why_human: "Category separation quality depends on LLM classification behavior, which requires a real extraction run to evaluate"
  - test: "Trigger POST twice rapidly for the same project"
    expected: "First call returns 202/200, second call returns 409 Conflict with clear error message"
    why_human: "Race condition behavior requires concurrent HTTP requests to test properly"
---

# Phase 4: Requirements Checklist Extraction — Verification Report

**Phase Goal:** User receives a categorized, evidence-backed requirements checklist covering all tender obligations
**Verified:** 2026-02-19
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | RequirementItem schema captures requirement text, mandatory flag, citation fields, and LLM confidence | VERIFIED | `app/schemas/checklist.py` L18-55: all fields present with Field descriptions and validators |
| 2 | CategoryExtractionResponse wraps a list of RequirementItem objects for instructor extraction | VERIFIED | `app/schemas/checklist.py` L58-72: items: list[RequirementItem] with reasoning field |
| 3 | VerifiedRequirement carries category, citation, NLI-adjusted confidence, and confidence_level | VERIFIED | `app/schemas/checklist.py` L75-115: category, citation(Citation), nli_score, confidence, confidence_level all present |
| 4 | RequirementsChecklist groups requirements, submission_documents, and eligibility_criteria | VERIFIED | `app/schemas/checklist.py` L118-150: three separate lists plus total_count, mandatory_count, categories_extracted |
| 5 | ChecklistResponse wraps API output with status, counts, and optional checklist data | VERIFIED | `app/schemas/checklist.py` L153-177: project_id, status, checklist, extraction_time_seconds, total_requirements, requirements_requiring_review |
| 6 | Six CategoryDefinition objects define queries, prompts, and retrieval parameters per category | VERIFIED | `app/services/extraction/checklist_definitions.py` L46-152: 6 entries, all with 3 queries, correct top_k/max_chunks per spec |
| 7 | build_checklist_extraction_prompt() returns a category-focused extraction prompt with labeled context | VERIFIED | `app/services/llm/context_builder.py` L89-133: function exists, generates prompt with category name, description, prompt_hints, skip-list, and DOCUMENT EXCERPTS label |
| 8 | ChecklistService extracts requirements from 6 categories using per-category hybrid search retrieval | VERIFIED | `app/services/extraction/checklist_service.py` L343-386: iterates CHECKLIST_CATEGORIES, calls _extract_category per category |
| 9 | Each category uses multiple search queries merged and deduplicated by chunk_id before LLM extraction | VERIFIED | `app/services/extraction/checklist_service.py` L70-104: seen_chunk_ids set, dedup by chunk.chunk_id, sorted by score, capped at max_context_chunks |
| 10 | GeminiService.extract() called with CategoryExtractionResponse wrapper model for each category | VERIFIED | `app/services/extraction/checklist_service.py` L146-150: asyncio.to_thread(self._llm_service.extract, ..., response_model=CategoryExtractionResponse) |
| 11 | Each extracted RequirementItem is verified via CitationVerifier NLI and gets three-signal confidence | VERIFIED | `app/services/extraction/checklist_service.py` L186-202: verify_citation() and calculate_confidence() called per item |
| 12 | Post-extraction semantic deduplication removes near-duplicate requirements across categories | VERIFIED | `app/services/extraction/checklist_service.py` L224-292: cosine similarity >= 0.9 threshold, numpy-based, lower-confidence item removed |
| 13 | Final checklist separates requirements vs submission_documents vs eligibility_criteria | VERIFIED | `app/services/extraction/checklist_service.py` L298-337: three-way split by category name in _assemble_checklist() |
| 14 | Individual category failures produce graceful degradation | VERIFIED | `app/services/extraction/checklist_service.py` L151-157: try/except around LLM call returns [] with warning log |
| 15 | POST /api/projects/{id}/checklist triggers checklist extraction and returns ChecklistResponse | VERIFIED | `app/api/checklist.py` L98-153: POST endpoint exists, calls extract_and_persist_checklist, returns ChecklistResponse |
| 16 | GET /api/projects/{id}/checklist returns stored checklist results without re-extraction | VERIFIED | `app/api/checklist.py` L156-227: GET endpoint reads checklist_json from DB, handles all 4 statuses |
| 17 | Project model has checklist_json and checklist_status columns | VERIFIED | `app/models/project.py` L35-38: both columns present as Mapped[str|None] with nullable=True |
| 18 | Checklist router is registered in main.py with /api prefix | VERIFIED | `app/main.py` L12, L78: imported as checklist_router, included with prefix="/api" |

**Score: 18/18 truths verified**

---

## Required Artifacts

| Artifact | Expected | Lines | Status | Details |
|----------|----------|-------|--------|---------|
| `app/schemas/checklist.py` | 5 Pydantic models; Citation from extraction | 177 | VERIFIED | All 5 models present; `from app.schemas.extraction import Citation`; Citation annotation confirmed at runtime |
| `app/services/extraction/checklist_definitions.py` | CategoryDefinition dataclass + 6 entries | 152 | VERIFIED | Dataclass with all required fields; 6 entries with exact chunk params per plan spec |
| `app/services/llm/context_builder.py` | build_checklist_extraction_prompt() added | N/A | VERIFIED | Function exists at L89; existing functions (build_labeled_context, build_extraction_prompt) unchanged |
| `app/services/extraction/checklist_service.py` | ChecklistService with 6 methods | 443 | VERIFIED | All 6 methods confirmed: _retrieve_category_chunks, _extract_category, _deduplicate, _assemble_checklist, extract_checklist, extract_and_persist_checklist |
| `app/models/project.py` | checklist_json and checklist_status columns | N/A | VERIFIED | Both columns on Project model; runtime check via `Project.__table__.columns` confirms keys |
| `app/api/checklist.py` | POST and GET /projects/{project_id}/checklist | 227 | VERIFIED | Both routes present; lazy singleton; 404/409/500 handling; all 4 status values handled in GET |
| `app/main.py` | Checklist router registered | N/A | VERIFIED | `from app.api.checklist import router as checklist_router` at L12; `app.include_router(checklist_router, prefix="/api")` at L78 |
| `app/services/extraction/__init__.py` | ChecklistService, CategoryDefinition, CHECKLIST_CATEGORIES exported | N/A | VERIFIED | All three in `__all__`; confirmed importable at runtime |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/schemas/checklist.py` | `app/schemas/extraction.py` | `from app.schemas.extraction import Citation` | WIRED | Pattern confirmed; runtime annotation check shows `<class 'app.schemas.extraction.Citation'>` |
| `app/services/extraction/checklist_definitions.py` | `app/services/llm/context_builder.py` | `CategoryDefinition` used in build_checklist_extraction_prompt | WIRED | Function signature accepts `category: CategoryDefinition`; TYPE_CHECKING guard used |
| `app/services/extraction/checklist_service.py` | `app/services/search/hybrid_search.py` | `self._search_service.search()` | WIRED | Pattern `self._search.*\.search\(` confirmed in _retrieve_category_chunks |
| `app/services/extraction/checklist_service.py` | `app/services/llm/gemini_service.py` | `self._llm_service.extract` via asyncio.to_thread | WIRED | `self._llm_service.extract` found at L147 (split across two lines with asyncio.to_thread) |
| `app/services/extraction/checklist_service.py` | `app/services/extraction/citation_verifier.py` | `self._citation_verifier.verify_citation()` and `.calculate_confidence()` | WIRED | Both calls confirmed in _extract_category; Note: plan specified `self._verifier.*` but implementation uses `self._citation_verifier.*` — functionally identical, attribute naming differs from plan pattern only |
| `app/services/extraction/checklist_service.py` | `app/schemas/checklist.py` | `from app.schemas.checklist import` | WIRED | Import at L25-29 confirmed |
| `app/services/extraction/checklist_service.py` | `app/services/extraction/checklist_definitions.py` | `from app.services.extraction.checklist_definitions import` | WIRED | Import at L31 confirmed |
| `app/api/checklist.py` | `app/services/extraction/checklist_service.py` | `_get_checklist_service()` lazy singleton | WIRED | Pattern present; lazy import inside function; singleton pattern confirmed |
| `app/api/checklist.py` | `app/schemas/checklist.py` | `from app.schemas.checklist import` | WIRED | L17: `from app.schemas.checklist import ChecklistResponse, RequirementsChecklist` |
| `app/api/checklist.py` | `app/models/project.py` | reads `project.checklist_json` and `project.checklist_status` | WIRED | Both attribute accesses confirmed in endpoint source |
| `app/main.py` | `app/api/checklist.py` | `from app.api.checklist import router as checklist_router` | WIRED | Exact import pattern confirmed at L12; `app.include_router(checklist_router, prefix="/api")` at L78 |

---

## Requirements Coverage

| Requirement | Description | Source Plans | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| CHK-01 | System extracts technical requirements from tender documents | 04-02, 04-03 | SATISFIED | CHECKLIST_CATEGORIES[0] name="technical"; extraction pipeline processes technical category |
| CHK-02 | System extracts commercial requirements | 04-02, 04-03 | SATISFIED | CHECKLIST_CATEGORIES[1] name="commercial" with commercial-specific queries and prompt_hints |
| CHK-03 | System extracts legal requirements | 04-02, 04-03 | SATISFIED | CHECKLIST_CATEGORIES[2] name="legal" defined and processed in pipeline |
| CHK-04 | System extracts HSE requirements | 04-02, 04-03 | SATISFIED | CHECKLIST_CATEGORIES[3] name="hse" defined with HSE-specific queries |
| CHK-05 | System categorizes requirements by type (Technical/Commercial/Legal/HSE) | 04-01, 04-03 | SATISFIED | VerifiedRequirement.category field carries category name; _assemble_checklist() groups by category; ChecklistResponse.checklist.requirements splits into typed groups |
| CHK-06 | System extracts mandatory submission documents list | 04-02, 04-03 | SATISFIED | CHECKLIST_CATEGORIES[4] name="submission_documents"; _assemble_checklist() places these in checklist.submission_documents list |
| CHK-07 | System detects eligibility/pre-qualification criteria | 04-02, 04-03 | SATISFIED | CHECKLIST_CATEGORIES[5] name="eligibility"; _assemble_checklist() places these in checklist.eligibility_criteria list |

All 7 Phase 4 requirements (CHK-01 through CHK-07) are SATISFIED. No orphaned requirements detected — REQUIREMENTS.md maps CHK-01..CHK-07 to Phase 4, and all are claimed across plans 04-01, 04-02, and 04-03.

---

## Anti-Patterns Found

No blocking or warning anti-patterns found.

Informational notes:
- `checklist_service.py` L138 and L157: `return []` statements are intentional graceful degradation (no-chunks path and LLM-failure path) — not stubs
- Plan 04-02 key_link pattern `self\._verifier\.(verify_citation|calculate_confidence)\(` does not match the implementation attribute name `self._citation_verifier.*` — the regex pattern in the plan was incorrect, but the functionality is fully wired. Not a code issue.

---

## Human Verification Required

### 1. End-to-End Extraction Run

**Test:** With a running server and a project with indexed tender documents, call `POST /api/projects/{id}/checklist`
**Expected:** Extraction completes across all 6 categories, returns `status=completed`, checklist contains non-empty requirements, submission_documents, and eligibility_criteria lists with valid citations
**Why human:** Requires real Gemini API key, real indexed documents, and a live server. Extraction quality and correctness of category separation cannot be verified statically.

### 2. Category Separation Quality

**Test:** Inspect the returned checklist and verify that technical requirements appear under `requirements`, submission documents appear under `submission_documents`, and eligibility criteria appear under `eligibility_criteria`
**Expected:** No category cross-contamination; HSE items not mixed with legal items, etc.
**Why human:** LLM classification behavior and prompt effectiveness can only be assessed against a real extraction result.

### 3. Concurrent Extraction Prevention (409)

**Test:** Trigger two simultaneous POST requests to `/api/projects/{id}/checklist` for the same project
**Expected:** One request succeeds and returns 200; the second returns 409 Conflict with message "Checklist extraction already in progress for this project"
**Why human:** Race condition testing requires concurrent HTTP clients; cannot verify with static analysis.

---

## Gaps Summary

No gaps. All must-haves from all three plans are implemented, substantive, and wired. All 7 CHK requirements are satisfied by the implemented pipeline.

The phase delivers:
- A complete Pydantic schema hierarchy (5 models) for checklist extraction
- Six CategoryDefinition entries covering all requirement types in construction tenders
- A ChecklistService orchestrating multi-query retrieval, Gemini LLM extraction, NLI citation verification, semantic deduplication, and three-way checklist assembly
- REST API endpoints (POST trigger, GET retrieve) with full error handling and status lifecycle
- Project model persistence columns and extraction package exports

The phase goal — "user receives a categorized, evidence-backed requirements checklist covering all tender obligations" — is structurally achieved. The pipeline is fully wired from API trigger through to database persistence and retrieval.

---

_Verified: 2026-02-19_
_Verifier: Claude (gsd-verifier)_
