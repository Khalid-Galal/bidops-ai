---
phase: 01-document-ingestion-pipeline
plan: 02
subsystem: parsing
tags: [docling, openpyxl, pdf, docx, xlsx, ocr, easyocr, dataclass, async]

# Dependency graph
requires:
  - phase: none
    provides: "First parsing module -- no prior dependencies"
provides:
  - "ParsedDocument and PageContent uniform output dataclasses"
  - "ParserInterface base class for format-specific parsers"
  - "PdfParser with Docling OCR and table extraction"
  - "DocxParser with Docling DOCX support"
  - "XlsxParser with openpyxl multi-sheet extraction"
  - "get_parser_for_file() registry routing by extension"
affects:
  - "01-03 (document upload service will orchestrate these parsers)"
  - "02-01 (Arabic OCR adds 'ar' to EasyOcrOptions lang list)"
  - "02-02 (vector indexing consumes ParsedDocument.full_text)"

# Tech tracking
tech-stack:
  added:
    - "docling (PDF/DOCX parsing with OCR and table structure)"
    - "openpyxl (XLSX parsing with read_only and data_only mode)"
    - "easyocr (via Docling EasyOcrOptions for scanned PDF OCR)"
  patterns:
    - "Lazy converter initialization (module-level _converter with _get_converter())"
    - "asyncio.to_thread() wrapping for all sync parsing operations"
    - "Graceful error handling returning ParsedDocument with warnings"
    - "Parser registry pattern with get_parser_for_file()"

key-files:
  created:
    - "app/__init__.py"
    - "app/services/__init__.py"
    - "app/services/parsing/__init__.py"
    - "app/services/parsing/base.py"
    - "app/services/parsing/pdf_parser.py"
    - "app/services/parsing/docx_parser.py"
    - "app/services/parsing/xlsx_parser.py"
  modified: []

key-decisions:
  - "Separate Docling converters for PDF and DOCX (different pipeline options)"
  - "openpyxl for XLSX instead of Docling (Docling XLSX has known edge cases)"
  - "Lazy converter initialization to avoid loading ~2GB models at import time"
  - "Each sheet treated as one 'page' in XLSX parsed output"

patterns-established:
  - "Parser registry: get_parser_for_file() routes by extension to parser instances"
  - "Uniform output: all parsers return ParsedDocument regardless of input format"
  - "Async wrapping: sync CPU-bound operations use asyncio.to_thread()"
  - "Graceful degradation: parse errors return empty ParsedDocument with warnings, never raise"

requirements-completed:
  - ING-01
  - ING-02
  - ING-03
  - LANG-02

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 1 Plan 2: Multi-Format Document Parsing Pipeline Summary

**Docling-based PDF/DOCX parsers with OCR and table extraction, openpyxl XLSX parser, unified ParsedDocument output, and extension-based parser registry**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-18T22:13:31Z
- **Completed:** 2026-02-18T22:20:42Z
- **Tasks:** 2
- **Files created:** 7

## Accomplishments
- Uniform ParsedDocument and PageContent dataclasses that all parsers produce regardless of input format
- PdfParser with Docling OCR (EasyOCR English), ACCURATE table structure mode, and lazy converter initialization
- DocxParser with Docling native DOCX support sharing the same iterate_items pattern
- XlsxParser with openpyxl read_only/data_only mode treating each sheet as a page with table extraction
- Parser registry (get_parser_for_file) that routes files to the correct parser by extension
- All sync parsing operations wrapped in asyncio.to_thread() to keep the event loop responsive

## Task Commits

Each task was committed atomically:

1. **Task 1: Create parser base types and PDF/DOCX parsers using Docling** - `81b08f9` (feat)
2. **Task 2: Create XLSX parser using openpyxl** - `a8568ff` (feat)

## Files Created/Modified
- `app/__init__.py` - Package root
- `app/services/__init__.py` - Services package
- `app/services/parsing/__init__.py` - Parsing package with re-exports and registry imports
- `app/services/parsing/base.py` - ParsedDocument, PageContent dataclasses, ParserInterface, get_parser_for_file()
- `app/services/parsing/pdf_parser.py` - Docling PDF parser with OCR and table extraction
- `app/services/parsing/docx_parser.py` - Docling DOCX parser
- `app/services/parsing/xlsx_parser.py` - openpyxl XLSX parser with multi-sheet support

## Decisions Made
- **Separate converters for PDF and DOCX:** PDF requires PdfPipelineOptions with OCR and table structure config; DOCX uses Docling defaults. Separate module-level caches avoid configuration conflicts.
- **openpyxl over Docling for XLSX:** Docling XLSX has known edge cases (no sheet selection, IndexError with some options). openpyxl is battle-tested and more reliable for Excel files.
- **Lazy converter initialization:** Docling downloads ~2GB of models on first use. Lazy init avoids blocking application startup and allows import without triggering downloads.
- **Sheets as pages:** Each Excel sheet maps to one PageContent entry with page_number = sheet index + 1, providing a consistent page-based model across all formats.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created XlsxParser stub in Task 1 for import chain**
- **Found during:** Task 1 (creating __init__.py and get_parser_for_file)
- **Issue:** The parsing __init__.py imports XlsxParser and get_parser_for_file() imports all three parsers. Without xlsx_parser.py existing, Task 1 verification would fail on ImportError.
- **Fix:** Created XlsxParser as a stub (with NotImplementedError in parse()) during Task 1, then fully implemented in Task 2.
- **Files modified:** app/services/parsing/xlsx_parser.py
- **Verification:** All Task 1 import verifications pass
- **Committed in:** 81b08f9 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for correct import chain. XlsxParser stub was replaced with full implementation in Task 2. No scope creep.

## Issues Encountered
None -- all verifications passed on first attempt.

## User Setup Required
None - no external service configuration required. Docling models will auto-download on first parse invocation (~2GB, requires internet).

## Next Phase Readiness
- Parser modules ready for Plan 03 (document upload service) to orchestrate
- get_parser_for_file() provides the single entry point for routing uploaded files to parsers
- ParsedDocument structure ready for downstream consumers (search indexing, vector storage)
- Arabic OCR support deferred to Phase 2 (add "ar" to EasyOcrOptions lang list)

---
*Phase: 01-document-ingestion-pipeline*
*Completed: 2026-02-19*
