---
phase: 03-project-summary-extraction
plan: 02
subsystem: extraction
tags: [nli, cross-encoder, deberta, citation-verification, confidence-scoring, sentence-transformers]

# Dependency graph
requires:
  - phase: 02-bilingual-processing-search
    provides: "SearchResult dataclass, sentence-transformers dependency, hybrid search service"
provides:
  - "CitationVerifier class with NLI-based citation verification"
  - "Independent entailment checking via cross-encoder model"
  - "Three-signal confidence scoring (NLI + retrieval + LLM)"
  - "Low-confidence field flagging for human review"
affects: [03-project-summary-extraction, 04-requirements-checklist]

# Tech tracking
tech-stack:
  added: [cross-encoder/nli-deberta-v3-xsmall]
  patterns: [lazy-model-loading, independent-verification, multi-signal-confidence]

key-files:
  created:
    - app/services/extraction/citation_verifier.py
  modified: []

key-decisions:
  - "NLI cross-encoder is independent from extraction LLM (avoids self-verification bias)"
  - "Lazy model loading to avoid startup delay (~22MB model downloads on first use)"
  - "Lenient NLI threshold (0.3) for keeping citations -- score still contributes to overall confidence"
  - "Confidence weights: NLI 50%, retrieval 30%, LLM 20% (NLI most trusted signal)"

patterns-established:
  - "Lazy model loading: expensive ML models loaded on first use, not at import/init time"
  - "Multi-signal confidence: combine independent signals with explicit weights for calibrated scoring"
  - "Graceful degradation: model failures return 0.0 score rather than raising exceptions"

requirements-completed: [CIT-01, CIT-02, CIT-03, CIT-04]

# Metrics
duration: 6min
completed: 2026-02-19
---

# Phase 3 Plan 2: Citation Verification Summary

**NLI cross-encoder (nli-deberta-v3-xsmall) independently verifies LLM citations via entailment checking, with three-signal confidence scoring (NLI 50% + retrieval 30% + LLM 20%)**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-19T09:55:52Z
- **Completed:** 2026-02-19T10:02:16Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- CitationVerifier uses independent NLI cross-encoder model to verify each citation's source text entails the extracted claim
- Softmax applied to raw model logits for calibrated entailment probabilities (0.0-1.0)
- Three-signal confidence scoring combines NLI entailment, retrieval relevance, and LLM self-confidence
- Low-confidence fields (below review_threshold=0.5) flagged with requires_review=True
- Citations failing NLI verification (entailment < 0.3) removed from field output
- Model loads lazily on first use -- no startup delay

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CitationVerifier with NLI cross-encoder and confidence scoring** - `e3c63eb` (feat)

## Files Created/Modified
- `app/services/extraction/citation_verifier.py` - NLI-based citation verification and confidence scoring service

## Decisions Made
- NLI cross-encoder is independent from extraction LLM -- avoids self-verification bias (Stanford research: 17-33% hallucination rate)
- Lenient NLI threshold (0.3) for keeping citations rather than strict cutoff, since the score flows into overall confidence
- Confidence weights: NLI 50%, retrieval 30%, LLM 20% -- NLI is most trusted as it is an independent model
- Fields without any verified citations capped at 0.3 confidence (max) to prevent overconfidence
- Softmax with numerical stability (subtract max before exp) applied to raw logits
- Source chunk matching falls back to filename-only if exact filename+page match fails (LLM may cite wrong page)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The NLI model (cross-encoder/nli-deberta-v3-xsmall, ~22MB) downloads automatically from HuggingFace on first use.

## Next Phase Readiness
- CitationVerifier ready to integrate with extraction pipeline (plan 03-03)
- Operates on ExtractedField and Citation schemas from plan 03-01
- verify_field() accepts SearchResult source chunks from Phase 2 hybrid search

---
*Phase: 03-project-summary-extraction*
*Completed: 2026-02-19*
