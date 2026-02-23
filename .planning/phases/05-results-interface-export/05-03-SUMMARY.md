---
phase: 05-results-interface-export
plan: 03
subsystem: api, export, ui
tags: [openpyxl, weasyprint, excel, pdf, jinja2, streaming-response]

# Dependency graph
requires:
  - phase: 05-02
    provides: "Project page with 4-tab layout, summary/checklist data endpoints"
  - phase: 03-03
    provides: "ProjectSummary schema and summary_json on Project model"
  - phase: 04-03
    provides: "RequirementsChecklist schema and checklist_json on Project model"
provides:
  - "Excel export service generating styled .xlsx with Summary and Checklist sheets"
  - "PDF export service generating formatted A4 report with WeasyPrint"
  - "GET /api/projects/{id}/export/excel and /export/pdf API endpoints"
  - "Export buttons on project page with blob download and loading state"
affects: []

# Tech tracking
tech-stack:
  added: [weasyprint]
  patterns: [streaming-blob-download, lazy-weasyprint-import, graceful-degradation-501]

key-files:
  created:
    - app/services/export/__init__.py
    - app/services/export/excel_export.py
    - app/services/export/pdf_export.py
    - app/api/export.py
    - app/templates/reports/pdf_report.html
    - app/static/css/pdf_report.css
  modified:
    - app/main.py
    - app/templates/project.html
    - app/static/css/styles.css
    - requirements.txt

key-decisions:
  - "Lazy WeasyPrint import with RuntimeError for graceful degradation when Pango not installed"
  - "Blob-based download in JS (createObjectURL + anchor click) for seamless file save"
  - "Separate PDF template directory (app/templates/reports/) isolated from web templates"

patterns-established:
  - "Streaming export: BytesIO buffer + StreamingResponse for memory-efficient file downloads"
  - "Graceful dependency degradation: 501 status with installation instructions for optional deps"

requirements-completed: [EXP-01, EXP-02]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 5 Plan 3: Export Services Summary

**Excel and PDF export endpoints with openpyxl workbooks, WeasyPrint PDF reports, and download buttons on project page**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T09:09:26Z
- **Completed:** 2026-02-23T09:13:23Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Excel export generates styled .xlsx with Summary (13 fields, confidence, citations) and Requirements Checklist (all categories) sheets
- PDF export generates formatted A4 report with cover section, summary table, checklist tables by category, and citation appendix on a new page
- Export buttons on project page with loading state ("Generating...") and blob-based download
- WeasyPrint graceful degradation: lazy import, RuntimeError with instructions, 501 HTTP response

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Excel and PDF export services** - `c6f5745` (feat)
2. **Task 2: Add export API endpoints and UI buttons** - `290b529` (feat)

**Plan metadata:** (pending final docs commit)

## Files Created/Modified
- `app/services/export/__init__.py` - Package init for export services
- `app/services/export/excel_export.py` - generate_excel_report() with openpyxl, styled headers, auto-fit columns
- `app/services/export/pdf_export.py` - generate_pdf_report() with WeasyPrint, Jinja2 template rendering
- `app/api/export.py` - GET /export/excel and /export/pdf endpoints with StreamingResponse
- `app/templates/reports/pdf_report.html` - Standalone HTML template for PDF with cover, summary, checklist, citation appendix
- `app/static/css/pdf_report.css` - Print-oriented CSS with @page A4 rules, confidence colors, page-break for appendix
- `app/main.py` - Added export_router registration
- `app/templates/project.html` - Added export bar with Excel/PDF buttons and downloadExport() JS function
- `app/static/css/styles.css` - Added .export-bar flex layout styles
- `requirements.txt` - Added weasyprint dependency

## Decisions Made
- Lazy WeasyPrint import with RuntimeError: avoids hard crash when Pango system library is missing, returns clear 501 with installation instructions
- Blob-based download in JavaScript: createObjectURL + temporary anchor element for seamless file save without page navigation
- Separate PDF template directory: app/templates/reports/ keeps WeasyPrint templates isolated from Jinja2 web templates (not extending base.html)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

WeasyPrint requires the Pango system library:
- **Windows:** MSYS2 -> `pacman -S mingw-w64-x86_64-pango`
- **Ubuntu:** `apt install libpango-1.0-0 libpangocairo-1.0-0`
- **macOS:** `brew install pango`

Then: `pip install weasyprint`

The system gracefully handles missing WeasyPrint (Excel export still works, PDF returns 501 with instructions).

## Next Phase Readiness
- Phase 5 is now complete -- all 3 plans executed (UI layout, search tab, export services)
- The full application is functional: document ingestion, text processing, search, extraction, checklist, and export
- End-to-end testing with real Arabic tender documents recommended

## Self-Check: PASSED

- All 6 created files verified present on disk
- Commit c6f5745 verified in git log
- Commit 290b529 verified in git log
- Export routes registered: /api/projects/{project_id}/export/excel, /api/projects/{project_id}/export/pdf

---
*Phase: 05-results-interface-export*
*Completed: 2026-02-23*
