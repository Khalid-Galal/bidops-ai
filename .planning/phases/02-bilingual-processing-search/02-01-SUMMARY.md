---
phase: 02-bilingual-processing-search
plan: 01
subsystem: text-processing
tags: [arabic, ocr, easyocr, pyarabic, lingua, bidi, normalization, language-detection, rtl]

# Dependency graph
requires:
  - phase: 01-document-ingestion-pipeline
    provides: "PdfParser with EasyOCR pipeline, ParsedDocument output"
provides:
  - "Arabic OCR support in PdfParser via EasyOCR lang=['en', 'ar']"
  - "Arabic text normalization pipeline (normalize_arabic, normalize_for_search)"
  - "Per-section language detection (detect_language, detect_languages_per_section)"
  - "Post-OCR text cleanup for Arabic and mixed content (clean_ocr_text)"
  - "text_processing package with clean re-exports for downstream consumers"
affects:
  - "02-02 (chunking service consumes normalize_for_search and detect_language for chunk metadata)"
  - "02-03 (search service uses normalize_for_search at query time for consistent matching)"
  - "03-xx (LLM extraction pipeline may use language detection for prompt selection)"

# Tech tracking
tech-stack:
  added:
    - "PyArabic (Arabic diacritics removal and text normalization)"
    - "python-bidi (Unicode BiDi algorithm for RTL/LTR text ordering)"
    - "lingua-language-detector (Rust-compiled per-section language detection)"
  patterns:
    - "Lazy detector initialization (module-level _detector with _get_detector())"
    - "Script-based pre-check before per-section language detection"
    - "PyArabic with regex fallback for diacritics removal"
    - "Normalize-at-both-ends pattern: normalize_for_search at index AND query time"

key-files:
  created:
    - "app/services/text_processing/__init__.py"
    - "app/services/text_processing/arabic_normalizer.py"
    - "app/services/text_processing/language_detector.py"
    - "app/services/text_processing/text_cleaner.py"
  modified:
    - "app/services/parsing/pdf_parser.py"
    - "requirements.txt"

key-decisions:
  - "Used PyArabic strip_tashkeel() with regex fallback rather than pure regex for diacritics removal"
  - "Script-based pre-check (Arabic+Latin chars present) triggers per-section detection for mixed language classification"
  - "Bidi correction only applied when suspicious number ordering detected (conservative heuristic to avoid unnecessary text changes)"

patterns-established:
  - "normalize_for_search() must be applied at BOTH index time and query time"
  - "Lazy module-level singleton pattern for expensive detector initialization"
  - "text_processing package re-exports for clean downstream imports"

requirements-completed: [LANG-01, LANG-03, LANG-04, LANG-05]

# Metrics
duration: 15min
completed: 2026-02-19
---

# Phase 2 Plan 1: Arabic OCR and Bilingual Text Processing Summary

**Arabic OCR via EasyOCR with PyArabic normalization pipeline, lingua per-section language detection, and post-OCR bidi-aware text cleanup**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-02-19
- **Completed:** 2026-02-19
- **Tasks:** 2/2
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments
- PdfParser now supports Arabic OCR alongside English via EasyOCR lang=["en", "ar"]
- Arabic normalizer handles diacritics, alef variants, teh marbuta, Eastern numerals, and whitespace in correct order
- Language detector classifies text as ar/en/mixed/unknown using script pre-check and lingua per-section detection
- Post-OCR text cleaner handles control chars, broken lam-alef ligatures, misplaced tashkeel, and bidi ordering

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Arabic OCR to PdfParser and create Arabic text normalization module** - `801c62f` (feat)
2. **Task 2: Create language detection and post-OCR text cleaning modules** - `19fe1cf` (feat)

## Files Created/Modified
- `app/services/parsing/pdf_parser.py` - Updated EasyOCR config to include Arabic, updated docstring and cache comment
- `app/services/text_processing/__init__.py` - Package init with re-exports for normalize_arabic, normalize_for_search, detect_language, detect_languages_per_section, clean_ocr_text
- `app/services/text_processing/arabic_normalizer.py` - normalize_arabic() and normalize_for_search() with PyArabic + regex fallback
- `app/services/text_processing/language_detector.py` - detect_language() and detect_languages_per_section() using lingua-language-detector
- `app/services/text_processing/text_cleaner.py` - clean_ocr_text() and clean_table_text() with Arabic-specific OCR artifact handling
- `requirements.txt` - Added PyArabic, python-bidi, lingua-language-detector

## Decisions Made
- **PyArabic with regex fallback:** Used PyArabic's strip_tashkeel() for diacritics removal as it handles edge cases (combining marks, stacking diacritics) better than pure regex. Regex fallback ensures the module works even if PyArabic is missing.
- **Script-based mixed detection:** Rather than relying solely on lingua's confidence threshold for "mixed" classification, added a script-based pre-check (presence of both Arabic and Latin characters) that triggers per-section detection. This correctly identifies mixed content even when lingua's overall confidence is high for one language.
- **Conservative bidi correction:** Only apply python-bidi's get_display() when suspicious number ordering is detected (digits directly adjacent to Arabic characters). This avoids unnecessary text changes that could corrupt correctly ordered content.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed regex replacement string for lam-alef ligature repair**
- **Found during:** Task 2 (text_cleaner.py implementation)
- **Issue:** Used raw string `r"\u0644\1"` in regex `.sub()` replacement, but `\u0644` is not interpreted as a Unicode escape in raw strings, causing `re.PatternError: bad escape \u`
- **Fix:** Changed to non-raw string with escaped backslash: `"\u0644\\1"` so lam character is correctly inserted
- **Files modified:** app/services/text_processing/text_cleaner.py
- **Verification:** clean_ocr_text() runs without error on test inputs
- **Committed in:** 19fe1cf (Task 2 commit)

**2. [Rule 1 - Bug] Fixed per-line whitespace stripping in text cleaner**
- **Found during:** Task 2 (text_cleaner.py verification)
- **Issue:** clean_ocr_text() collapsed multiple spaces but left leading/trailing spaces on individual lines, producing `' hello world \n\n test '` instead of `'hello world\n\ntest'`
- **Fix:** Added `.strip()` to each line during per-line whitespace normalization
- **Files modified:** app/services/text_processing/text_cleaner.py
- **Verification:** `clean_ocr_text('  hello   world  \n\n\n\n  test  ')` returns `'hello world\n\ntest'`
- **Committed in:** 19fe1cf (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
- **Windows console encoding:** Arabic text output fails on Windows cp1252 console. Resolved by using `sys.stdout.reconfigure(encoding='utf-8')` in verification commands. This is a development environment issue, not a code issue.
- **Lingua mixed detection edge case:** For text with very few Arabic words among many English words (e.g., "Hello مرحبا mixed text content here"), lingua's `detect_multiple_languages_of()` classifies the entire segment as English. The script-based pre-check partially addresses this, but extremely lopsided content may still classify as the dominant language. This is acceptable behavior -- `detect_languages_per_section()` provides fine-grained detection when needed.

## User Setup Required

None - no external service configuration required. PyArabic, python-bidi, and lingua-language-detector install via pip from requirements.txt.

## Next Phase Readiness
- text_processing package ready for consumption by chunking service (Plan 02-02)
- normalize_for_search() and detect_language() are the primary interfaces for downstream use
- All functions importable via `from app.services.text_processing import ...`
- No blockers for Plan 02-02 (semantic chunking and vector indexing)

---
*Phase: 02-bilingual-processing-search*
*Plan: 01*
*Completed: 2026-02-19*
