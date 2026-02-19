---
phase: 03-project-summary-extraction
verified: 2026-02-19T10:16:19Z
status: passed
score: 13/13 must-haves verified
gaps: []
human_verification:
  - test: POST /api/projects/{id}/extract with real indexed project and valid BIDOPS_GEMINI_API_KEY
    expected: ExtractionResponse with 13 ExtractedField entries, each having citations (document_name + page_number + quote), confidence_level (high/medium/low), and requires_review flag
    why_human: Requires live Gemini API key and real indexed tender documents. NLI model downloads ~22MB on first run. Cannot verify LLM output quality programmatically.
  - test: GET /api/projects/{id}/extract after POST completes
    expected: Returns ExtractionResponse from project.summary_json without re-triggering extraction
    why_human: Requires live database with prior completed extraction to validate JSON persistence round-trip.
  - test: POST /api/projects/{id}/extract while extraction is in_progress
    expected: HTTP 409 Conflict -- Extraction already in progress for this project
    why_human: Code guard is structurally verified but race condition behavior needs live concurrent HTTP testing.
---

# Phase 3: Project Summary Extraction -- Verification Report

**Phase Goal:** User receives a complete, citation-backed project summary extracted from tender documents with confidence indicators
**Verified:** 2026-02-19T10:16:19Z
**Status:** PASSED
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User triggers extraction and receives a complete ProjectSummary with all 13 fields | VERIFIED | ExtractionService.extract_project_summary() iterates SUMMARY_FIELDS (13 entries), returns ProjectSummary(**results) |
| 2 | Each extracted field has citations with source document name and page number | VERIFIED | Citation schema enforces document_name: str and page_number: int (ge=1); ExtractedField.citations: list[Citation] |
| 3 | Each extracted field includes an exact verbatim quote from the source | VERIFIED | Citation.quote: str (min_length=1, description=Exact verbatim quote); LLM prompt instruction 3 enforces verbatim copy |
| 4 | Each field has a confidence score (high/medium/low) from NLI verification | VERIFIED | CitationVerifier.calculate_confidence() -- NLI 50% + retrieval 30% + LLM 20%; sets confidence_level and confidence on ExtractedField |
| 5 | Low-confidence fields are flagged with requires_review=True | VERIFIED | requires_review = score < self._review_threshold (0.5); also True when field has no verified citations |
| 6 | Extraction results are persisted to Project model as JSON | VERIFIED | project.summary_json = summary.model_dump_json() in extract_and_persist(); Project.summary_json: Mapped[str or None] mapped_column(Text) |
| 7 | Extraction uses per-field retrieval from hybrid search, not full-document-to-LLM | VERIFIED | 13 separate search calls: for field_def in SUMMARY_FIELDS: self._search_service.search(query=field_def.query, top_k=field_def.top_k) |
| 8 | GeminiService wraps instructor for structured Pydantic output with validation retry | VERIFIED | instructor.from_provider(google/model, api_key=...) + client.create(response_model=response_model, max_retries=3) |
| 9 | CitationVerifier uses independent NLI model, not LLM self-verification | VERIFIED | CrossEncoder(cross-encoder/nli-deberta-v3-xsmall) loaded lazily; completely separate from GeminiService |
| 10 | Confidence combines three independent signals: NLI, retrieval, LLM | VERIFIED | score = nli_entailment_score * 0.5 + retrieval_score * 0.3 + llm_confidence * 0.2 |
| 11 | Citations failing NLI verification are removed | VERIFIED | if score >= 0.3: verified_citations.append(citation) else dropped; field.citations = verified_citations |
| 12 | POST /api/projects/{id}/extract is registered and reachable | VERIFIED | router.post(/projects/{project_id}/extract) in app/api/extraction.py; app.include_router(extraction_router, prefix=/api) in main.py |
| 13 | GET endpoint returns stored results without re-extraction | VERIFIED | ProjectSummary.model_validate_json(project.summary_json) in GET handler; no ExtractionService call on GET |

**Score:** 13/13 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| app/schemas/extraction.py | Citation, ExtractedField, LLMExtractedField, ProjectSummary, ExtractionResponse | VERIFIED | 128 lines; all 5 models present; Citation enforces document_name + page_number + quote; ProjectSummary has all 13 ExtractedField fields |
| app/services/extraction/field_definitions.py | FieldDefinition dataclass + 13 SUMMARY_FIELDS | VERIFIED | 136 lines; FieldDefinition with name, description, field_type, query, query_hints, top_k, required, enum_values; SUMMARY_FIELDS has exactly 13 entries |
| app/services/llm/gemini_service.py | Instructor-wrapped Gemini client with lazy init | VERIFIED | 97 lines; lazy _get_client() using instructor.from_provider(google/...); @retry for network errors; extract() with response_model |
| app/services/llm/context_builder.py | build_labeled_context + build_extraction_prompt | VERIFIED | 87 lines; [SOURCE:filename | PAGE:N] label format; date and list type-specific prompt extensions |
| app/services/extraction/citation_verifier.py | NLI-based citation verification and confidence scoring | VERIFIED | 272 lines; CrossEncoder lazy-loaded; softmax on raw logits; verify_citation(), verify_field(), calculate_confidence() all implemented |
| app/services/extraction/extraction_service.py | Orchestrates per-field retrieval + LLM + NLI verification | VERIFIED | 223 lines; 7-step pipeline per field; extract_and_persist() with in_progress/completed/failed status lifecycle |
| app/api/extraction.py | POST + GET /api/projects/{id}/extract | VERIFIED | 223 lines; both endpoints implemented; lazy singleton; 404/409/500 error handling |
| app/models/project.py | summary_json + extraction_status columns | VERIFIED | summary_json: Mapped[str or None] = mapped_column(Text, nullable=True); extraction_status: Mapped[str or None] = mapped_column(String(20)) |
| app/config.py | gemini_api_key, gemini_model, nli_model, confidence thresholds | VERIFIED | gemini_api_key, gemini_model (gemini-2.5-pro), nli_model, confidence_high_threshold, confidence_low_threshold, review_threshold -- all with BIDOPS_ prefix |
| app/services/extraction/__init__.py | Re-exports CitationVerifier, ExtractionService, FieldDefinition, SUMMARY_FIELDS | VERIFIED | All 4 symbols in __all__; direct imports (not TYPE_CHECKING) |
| app/services/llm/__init__.py | Re-exports GeminiService, build_labeled_context, build_extraction_prompt | VERIFIED | All 3 symbols in __all__ |
| requirements.txt | google-genai, instructor, tenacity | VERIFIED | All 3 listed under LLM integration (Phase 3) comment |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app/services/llm/gemini_service.py | instructor + google-genai | instructor.from_provider(google/model, api_key=...) | WIRED | Line 50-53: lazy client creates instructor-wrapped Gemini client on first extract call |
| app/services/llm/context_builder.py | SearchResult (hybrid_search) | TYPE_CHECKING import; chunk.filename, chunk.page_number, chunk.text | WIRED | Line 15: TYPE_CHECKING guard; line 32: [SOURCE:{chunk.filename} | PAGE:{chunk.page_number}] label |
| app/services/extraction/citation_verifier.py | sentence_transformers.CrossEncoder | CrossEncoder(self._model_name) in _get_model() | WIRED | Line 24: direct import; line 71: lazy model load on first verify_citation() call |
| app/services/extraction/citation_verifier.py | app/schemas/extraction.py | TYPE_CHECKING: Citation, ExtractedField | WIRED | Lines 27-28; verify_field() operates on ExtractedField; _find_source_chunk() matches Citation.document_name + page_number |
| app/services/extraction/extraction_service.py | HybridSearchService | self._search_service.search(project_id, query, top_k, mode=hybrid) | WIRED | Line 79-84: per-field search call inside SUMMARY_FIELDS loop |
| app/services/extraction/extraction_service.py | GeminiService | await asyncio.to_thread(self._llm_service.extract, prompt, response_model=LLMExtractedField) | WIRED | Line 107-111: async thread dispatch for synchronous LLM call |
| app/services/extraction/extraction_service.py | CitationVerifier | self._citation_verifier.verify_field(field, source_chunks, retrieval_scores) | WIRED | Line 138-142: NLI verification call after each LLM extraction |
| app/api/extraction.py | ExtractionService | extraction_service.extract_and_persist(project_id) | WIRED | Line 137: POST handler calls extract_and_persist; service composed lazily in _get_extraction_service() |
| app/main.py | app/api/extraction.py | app.include_router(extraction_router, prefix=/api) | WIRED | Line 13: import as extraction_router; line 76: registered with /api prefix |

---

## Requirements Coverage

| Requirement | Description | Status | Supporting Artifacts |
|-------------|-------------|--------|----------------------|
| SUM-01 | User receives extracted project name, owner, and location | SATISFIED | SUMMARY_FIELDS: project_name (text), project_owner (text), location (text); all 3 in ProjectSummary |
| SUM-02 | User receives key dates (submission deadline, validity, pre-bid meeting) | SATISFIED | SUMMARY_FIELDS: submission_deadline (date), bid_validity_period (text), pre_bid_meeting_date (date); all 3 in ProjectSummary |
| SUM-03 | User receives scope of work summary | SATISFIED | SUMMARY_FIELDS: scope_of_work (text, top_k=8 for broader coverage); ProjectSummary.scope_of_work: ExtractedField |
| SUM-04 | User receives contract type (lump sum, remeasured, etc.) | SATISFIED | SUMMARY_FIELDS: contract_type (enum) with enum_values=[lump_sum, remeasured, unit_rate, cost_plus, design_build, other] |
| SUM-05 | User receives financial terms (tender bond, advance %, retention %, payment terms) | SATISFIED | SUMMARY_FIELDS: tender_bond (currency), advance_payment, retention_percentage, payment_terms; all 4 in ProjectSummary |
| SUM-06 | User receives stakeholder list (consultants, PMC, designer) | SATISFIED | SUMMARY_FIELDS: stakeholders (list, top_k=5); build_extraction_prompt appends comma-separated list instruction |
| CIT-01 | Every extracted value links to source document and page number | SATISFIED | Citation.document_name: str + Citation.page_number: int (ge=1); embedded in every ExtractedField.citations |
| CIT-02 | User can see exact quote from source document for each extraction | SATISFIED | Citation.quote: str (min_length=1, Exact verbatim quote); LLM prompt instruction 3 enforces verbatim copy, not paraphrase |
| CIT-03 | System assigns confidence scores (high/medium/low) to each extraction | SATISFIED | ExtractedField.confidence_level: str (high/medium/low); ExtractedField.confidence: float (0.0-1.0); from calculate_confidence() |
| CIT-04 | System flags low-confidence items for human review | SATISFIED | ExtractedField.requires_review: bool; True when score < review_threshold (0.5); also True when no verified citations |

**All 10 phase requirements: SATISFIED**

---

## Anti-Patterns Found

No anti-patterns detected across all 7 phase 3 source files:

| File | Pattern Checked | Result |
|------|----------------|--------|
| app/schemas/extraction.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |
| app/services/extraction/field_definitions.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |
| app/services/llm/gemini_service.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |
| app/services/llm/context_builder.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |
| app/services/extraction/citation_verifier.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |
| app/services/extraction/extraction_service.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |
| app/api/extraction.py | TODO/FIXME/placeholder/empty returns/stub patterns | None found |

---

## Human Verification Required

### 1. End-to-End Extraction with Live API

**Test:** Configure BIDOPS_GEMINI_API_KEY in .env, index a real tender document via Phase 2 pipeline, then call POST /api/projects/{id}/extract
**Expected:** Response contains ExtractionResponse with status=completed, ProjectSummary with 13 fields populated, each field having citations with document_name + page_number + verbatim quote, and confidence_level set to high/medium/low
**Why human:** Requires live Gemini API key + NLI model download (~22MB first run) + real indexed tender documents. LLM output quality and citation accuracy cannot be verified structurally.

### 2. Stored Results Round-Trip

**Test:** After a successful POST extraction, call GET /api/projects/{id}/extract
**Expected:** Returns same ExtractionResponse from project.summary_json without calling Gemini -- response is parsed from stored JSON via ProjectSummary.model_validate_json()
**Why human:** Requires live database with prior completed extraction to validate JSON persistence and deserialization round-trip.

### 3. Duplicate Extraction Prevention

**Test:** Trigger two concurrent POST requests to /api/projects/{id}/extract
**Expected:** Second request returns HTTP 409 Conflict with message Extraction already in progress for this project
**Why human:** Code guard at lines 128-132 of app/api/extraction.py is structurally verified, but race condition behavior needs live concurrent HTTP testing.

---

## Summary

Phase 3 goal is fully achieved at the code level. All 13 observable truths are verified against actual codebase artifacts -- no stubs, no orphaned files, no broken wiring.

The extraction pipeline is complete and correctly wired end-to-end:

1. Schemas (app/schemas/extraction.py): Citation (document_name + page_number + quote), LLMExtractedField (LLM-facing, excludes post-processing fields), ExtractedField (full with confidence_level + requires_review), ProjectSummary (all 13 fields), ExtractionResponse (API wrapper with field counts).

2. Field definitions (app/services/extraction/field_definitions.py): All 13 SUMMARY_FIELDS with appropriate queries, top_k values, and field types. Covers SUM-01 (name/owner/location), SUM-02 (dates), SUM-03 (scope), SUM-04 (contract type with enum validation), SUM-05 (financial terms x4), SUM-06 (stakeholders as list).

3. LLM service (app/services/llm/gemini_service.py): Instructor-wrapped Gemini via instructor.from_provider(), lazy client initialization, tenacity retry for transient network errors only. Instructor manages validation retries internally via max_retries=3.

4. Context builder (app/services/llm/context_builder.py): [SOURCE:filename | PAGE:N] labels align with the citation format LLM is instructed to populate. Field-type-specific prompt extensions: date (preserve format), list (comma-separated output).

5. Citation verifier (app/services/extraction/citation_verifier.py): Independent NLI cross-encoder (not the LLM), softmax on raw logits for calibrated probabilities, three-signal confidence weighting (NLI 50% + retrieval 30% + LLM 20%), lazy model loading.

6. Extraction orchestrator (app/services/extraction/extraction_service.py): Full 7-step per-field pipeline (search -> context -> prompt -> LLM -> convert -> verify -> store). Graceful field-level failure handling. extract_and_persist() tracks in_progress/completed/failed status.

7. API (app/api/extraction.py): POST trigger + GET retrieval endpoints with lazy singleton service composition. 404 (project not found), 409 (already in progress), 500 (extraction failed) guards. Registered in main.py with /api prefix.

8. Database (app/models/project.py): summary_json (Text) and extraction_status (String(20)) columns correctly added after failed_documents column.

Three items require human verification with live Gemini API access -- functional and behavioral checks that cannot be determined from code structure alone.

---

_Verified: 2026-02-19T10:16:19Z_
_Verifier: Claude (gsd-verifier)_
