# Phase 5: Results Interface & Export - Research

**Researched:** 2026-02-19
**Domain:** Web UI (Jinja2 SSR + vanilla JS), Excel export (openpyxl), PDF export (WeasyPrint)
**Confidence:** HIGH

## Summary

Phase 5 builds the user-facing results interface and export capabilities on top of the existing FastAPI + Jinja2 server-side rendering architecture. The existing codebase already has all the backend API endpoints needed (extraction GET, checklist GET, search GET) and Pydantic schemas with rich data structures including citations, confidence levels, and review flags. The work is primarily (a) new Jinja2 templates and vanilla JS to display and interact with this data, (b) a PATCH endpoint to support checklist editing, and (c) two new export service modules that generate Excel and PDF files from the stored JSON data.

openpyxl is already a project dependency and is the standard choice for Excel generation. For PDF generation, **WeasyPrint** is the recommended choice because it converts HTML+CSS to PDF, meaning we can reuse Jinja2 templates and CSS styling from the web UI. WeasyPrint v65+ has fixed the RTL Arabic text duplication bug, and its HTML/CSS approach naturally handles `direction: rtl` for Arabic content. This avoids learning a completely separate layout API (like ReportLab's canvas) and keeps the PDF output visually consistent with the web interface.

**Primary recommendation:** Extend the existing project.html page with tabbed sections (Summary, Checklist, Search, Export) using vanilla JS tab switching. Add a PATCH API endpoint for checklist item updates. Create `app/services/export/` with `excel_export.py` (openpyxl + BytesIO) and `pdf_export.py` (WeasyPrint + Jinja2 templates). Serve exports via GET endpoints returning StreamingResponse.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-02 | User can view project summaries in the web interface | Jinja2 template rendering of ProjectSummary JSON with ExtractedField cards showing value, confidence badge, citations, and review flag. Data already available via GET /api/projects/{id}/extract. |
| UI-03 | User can view and edit requirements checklists in the web interface | Jinja2 template rendering of RequirementsChecklist with three category groups. Needs new PATCH /api/projects/{id}/checklist/items endpoint for toggling check-off and editing fields. Uses flag_modified() for SQLAlchemy JSON column updates. |
| UI-04 | User can search documents from the web interface | Search form + results display using GET /api/projects/{id}/search?q=... API. Vanilla JS fetch with debounce, results rendered with highlighted text, source metadata, and page numbers. |
| EXP-01 | User can export checklists and summaries to Excel | openpyxl (already installed) generating styled .xlsx with two sheets: Summary (field/value/confidence/citation table) and Checklist (requirement/category/mandatory/status/citation table). Served via StreamingResponse from BytesIO. |
| EXP-02 | User can export formatted reports to PDF | WeasyPrint (new dependency) converting Jinja2 HTML templates to PDF. Dedicated report template with cover page, summary section, checklist section, and citation appendix. CSS handles RTL Arabic text via direction:rtl. Served via StreamingResponse. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openpyxl | 3.1.x | Excel (.xlsx) generation with styling | Already in requirements.txt; native Python, no external dependencies; supports fonts, fills, borders, alignment, number formats |
| WeasyPrint | 68.x | HTML/CSS to PDF conversion | Reuses Jinja2+CSS (same toolchain as web UI); RTL Arabic fixed in v65+; pure pip install on modern systems; no need for wkhtmltopdf binary |
| Jinja2 | 3.x | Template rendering for both web UI and PDF | Already in requirements.txt; used by FastAPI for SSR pages; same templates can serve web and PDF |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| BytesIO (stdlib) | -- | In-memory file buffer | For Excel/PDF generation without temp files; pass directly to StreamingResponse |
| StreamingResponse (starlette) | -- | File download responses | Return generated files with proper Content-Type and Content-Disposition headers |
| flag_modified (sqlalchemy) | -- | Mark JSON columns as changed | Required when updating checklist_json in-place; SQLAlchemy does not auto-detect JSON mutations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WeasyPrint | fpdf2 | fpdf2 has a known bug with multi-line RTL text (lines render bottom-to-top); requires learning fpdf2's imperative API instead of reusing HTML/CSS |
| WeasyPrint | ReportLab | ReportLab 4.4+ has initial RTL support but requires learning Platypus/canvas API; HTML/CSS approach is simpler for this team |
| WeasyPrint | xhtml2pdf | xhtml2pdf's RTL support is incomplete and experimental; not recommended for Arabic content |
| openpyxl (direct) | pandas + openpyxl | pandas adds unnecessary overhead for simple structured data; openpyxl's Workbook API is more direct and allows full styling control |

**Installation:**
```bash
pip install weasyprint
```

**Note:** WeasyPrint requires Pango system library. On Windows, install via MSYS2: `pacman -S mingw-w64-x86_64-pango`. On Ubuntu/Debian: `apt install libpango-1.0-0 libpangocairo-1.0-0`. On macOS: `brew install pango`.

## Architecture Patterns

### Recommended Project Structure
```
app/
├── api/
│   ├── pages.py              # ADD: new page routes for results tabs
│   ├── checklist.py           # MODIFY: add PATCH endpoint for item updates
│   └── export.py              # NEW: export download endpoints
├── services/
│   └── export/
│       ├── __init__.py
│       ├── excel_export.py    # NEW: openpyxl Excel generation
│       └── pdf_export.py      # NEW: WeasyPrint PDF generation
├── templates/
│   ├── base.html              # EXISTING (unchanged)
│   ├── index.html             # EXISTING (unchanged)
│   ├── project.html           # MODIFY: add tab navigation, results sections
│   └── reports/
│       └── pdf_report.html    # NEW: dedicated PDF report template
└── static/
    └── css/
        └── styles.css         # MODIFY: add styles for tabs, summary, checklist, search
```

### Pattern 1: Tab Navigation (vanilla JS, no framework)
**What:** Client-side tab switching within the project detail page
**When to use:** When different data views exist for the same entity and all data is fetched on demand
**Example:**
```html
<!-- Tab buttons -->
<div class="tabs">
    <button class="tab active" data-tab="documents">Documents</button>
    <button class="tab" data-tab="summary">Summary</button>
    <button class="tab" data-tab="checklist">Checklist</button>
    <button class="tab" data-tab="search">Search</button>
</div>

<!-- Tab content panels -->
<div class="tab-content active" id="tab-documents">...</div>
<div class="tab-content" id="tab-summary">...</div>
<div class="tab-content" id="tab-checklist">...</div>
<div class="tab-content" id="tab-search">...</div>

<script>
document.querySelectorAll('.tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
        // Deactivate all tabs and panels
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
        // Activate clicked tab and its panel
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        // Lazy-load data on first tab activation
        if (!tab.dataset.loaded) {
            loadTabData(tab.dataset.tab);
            tab.dataset.loaded = 'true';
        }
    });
});
</script>
```

### Pattern 2: Lazy Data Loading via fetch()
**What:** Fetch JSON from existing API endpoints and render into DOM on tab activation
**When to use:** For Summary and Checklist tabs where data may not yet exist (extraction not run)
**Example:**
```javascript
async function loadSummary(projectId) {
    const response = await fetch('/api/projects/' + projectId + '/extract');
    const data = await response.json();

    if (data.status === 'not_started') {
        container.innerHTML = '<div class="empty-state"><p>No extraction results yet.</p>' +
            '<button class="btn btn-primary" onclick="triggerExtraction()">Run Extraction</button></div>';
        return;
    }

    if (data.status === 'completed' && data.summary) {
        renderSummaryFields(data.summary);
    }
}
```

### Pattern 3: Inline Checklist Editing with Optimistic Updates
**What:** Toggle checkbox or edit text, immediately update UI, then persist via PATCH
**When to use:** Checklist item check-off and description editing
**Example:**
```javascript
async function toggleChecklistItem(projectId, itemIndex, category, checked) {
    // Optimistic UI update
    const checkbox = document.getElementById('check-' + category + '-' + itemIndex);
    checkbox.checked = checked;

    try {
        await fetch('/api/projects/' + projectId + '/checklist/items', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category: category,
                index: itemIndex,
                updates: { checked: checked }
            })
        });
    } catch (err) {
        // Revert on failure
        checkbox.checked = !checked;
        showMessage('Failed to save: ' + err.message, 'error');
    }
}
```

### Pattern 4: Export Download via fetch + Blob
**What:** Trigger file download from API endpoint without page navigation
**When to use:** Excel and PDF export buttons
**Example:**
```javascript
async function downloadExport(projectId, format) {
    const btn = document.getElementById('export-' + format + '-btn');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const response = await fetch('/api/projects/' + projectId + '/export/' + format);
        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = response.headers.get('Content-Disposition')
            ?.split('filename=')[1]?.replace(/"/g, '') || 'export.' + format;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        showMessage('Export failed: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Export ' + format.toUpperCase();
    }
}
```

### Pattern 5: FastAPI StreamingResponse for File Downloads
**What:** Return in-memory generated files as HTTP responses with download headers
**When to use:** All export endpoints
**Example:**
```python
from io import BytesIO
from fastapi.responses import StreamingResponse

@router.get("/projects/{project_id}/export/excel")
async def export_excel(project_id: int):
    # Generate Excel in memory
    buffer = BytesIO()
    workbook = create_project_excel(project_id)  # returns openpyxl Workbook
    workbook.save(buffer)
    buffer.seek(0)

    filename = f"project_{project_id}_report.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

### Pattern 6: JSON Column Update with flag_modified
**What:** Update a field within a JSON column and ensure SQLAlchemy detects the change
**When to use:** Checklist item updates (check-off, text edits)
**Example:**
```python
from sqlalchemy.orm.attributes import flag_modified

async def update_checklist_item(project_id, category, index, updates):
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        checklist_data = json.loads(project.checklist_json)

        # Modify the specific item
        checklist_data[category][index].update(updates)

        # Persist
        project.checklist_json = json.dumps(checklist_data)
        flag_modified(project, "checklist_json")
        await session.commit()
```

### Anti-Patterns to Avoid
- **Full page reload for every interaction:** Use fetch() + DOM manipulation for tab switching, search, and checklist edits. Only reload for major state changes (like triggering extraction).
- **Storing export files on disk:** Generate in BytesIO and stream directly. No temp file cleanup needed.
- **Building a separate SPA framework:** This is a server-rendered app with progressive enhancement. Keep using Jinja2 + vanilla JS. Do not introduce React, Vue, or Alpine.
- **Fetching all data on page load:** Use lazy loading per tab. Summary and checklist data can be large; only fetch when the user clicks the tab.
- **Direct JSON manipulation without validation:** When updating checklist items via PATCH, parse with Pydantic schema first, then serialize back. Do not directly manipulate raw JSON strings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Excel file generation | Custom CSV-to-XLSX converter | openpyxl Workbook API | Cell styling, multiple sheets, proper .xlsx format, Unicode support all built-in |
| HTML to PDF conversion | Custom PDF layout engine | WeasyPrint | CSS layout, page breaks, headers/footers, Unicode/RTL all handled by mature library |
| Arabic RTL in PDF | Manual glyph reordering | WeasyPrint + CSS `direction: rtl` | Unicode BiDi algorithm is extremely complex; WeasyPrint handles it via Pango |
| File download responses | Manual chunked response building | FastAPI StreamingResponse | Handles HTTP headers, streaming, memory efficiency automatically |
| Tab UI component | Custom visibility toggling | Simple data-attribute pattern | 15 lines of vanilla JS; no library needed but must be consistent |
| JSON mutation detection | Manual dirty-flag tracking | SQLAlchemy flag_modified() | Standard ORM pattern; forgetting this is the #1 cause of "saves don't persist" bugs |

**Key insight:** This phase is almost entirely "glue" -- connecting existing API data to visual templates and existing libraries to export formats. Resist the urge to build custom infrastructure.

## Common Pitfalls

### Pitfall 1: SQLAlchemy JSON Column Mutations Not Detected
**What goes wrong:** You modify a dict parsed from a JSON column, re-serialize it, assign it back, but the change never persists to the database.
**Why it happens:** SQLAlchemy tracks changes by object identity. If you assign a new string to a `Text` column, it detects the change. But if you modify the same string or replace with an "equal" string, it may not detect it depending on the ORM internals.
**How to avoid:** Always call `flag_modified(instance, "column_name")` after updating JSON text columns. Or use `sqlalchemy.types.JSON` with `mutable=True` if switching column types is an option.
**Warning signs:** Checklist edits appear to save (no error) but revert on page reload.

### Pitfall 2: WeasyPrint Missing System Dependencies
**What goes wrong:** `pip install weasyprint` succeeds but `import weasyprint` or PDF generation fails with errors about Pango, Cairo, or GDK-PixBuf.
**Why it happens:** WeasyPrint requires Pango (and its transitive dependencies Cairo, GLib) as system libraries, not Python packages.
**How to avoid:** Document installation steps per platform. On Windows, install MSYS2 and run `pacman -S mingw-w64-x86_64-pango`. Add to project setup docs. Test import early.
**Warning signs:** `OSError: cannot load library` or `ctypes` errors on first run.

### Pitfall 3: Arabic Font Not Embedded in PDF
**What goes wrong:** Arabic text renders as boxes or question marks in the PDF output.
**Why it happens:** The default system fonts may not include Arabic glyph coverage. WeasyPrint needs a font that supports Arabic Unicode ranges.
**How to avoid:** Include an Arabic-capable font (e.g., Noto Sans Arabic, Amiri) in the project's static/fonts/ directory and reference it via CSS `@font-face` in the PDF template. Do not rely on system fonts.
**Warning signs:** English text renders fine but Arabic text shows rectangles or is missing.

### Pitfall 4: Content-Disposition Header Encoding for Non-ASCII Filenames
**What goes wrong:** Filenames with Arabic or special characters cause download issues in some browsers.
**Why it happens:** HTTP headers are ASCII-only by default. Non-ASCII filenames need RFC 5987 encoding.
**How to avoid:** Use ASCII-safe filenames for downloads (e.g., `project_42_report.xlsx`). Avoid putting Arabic text in filenames. If needed, use `filename*=UTF-8''encoded_name` header format.
**Warning signs:** File downloads with garbled names or browser errors.

### Pitfall 5: Large Checklist JSON Causing Slow PATCH Updates
**What goes wrong:** Updating a single checkbox requires parsing and re-serializing the entire checklist JSON.
**Why it happens:** Checklist data is stored as a single JSON text column, not as individual rows.
**How to avoid:** This is acceptable for v1 (checklists are typically <500 items, <100KB JSON). Just parse, modify, serialize, save. Do not prematurely optimize by splitting into a separate table.
**Warning signs:** None for v1 scale. Would matter at 10k+ items.

### Pitfall 6: Export Buttons Triggering Multiple Requests
**What goes wrong:** User clicks Export multiple times, spawning multiple PDF generation processes.
**Why it happens:** No button disable logic during generation.
**How to avoid:** Disable button immediately on click, show "Generating..." text, re-enable after download completes or fails. Pattern shown in the export download code example above.
**Warning signs:** Multiple identical downloads appearing, server load spikes.

## Code Examples

Verified patterns from official sources and codebase analysis:

### Excel Export with openpyxl (Summary Sheet)
```python
# Source: openpyxl docs + project schema analysis
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def create_summary_sheet(wb: Workbook, summary_data: dict) -> None:
    """Create the Project Summary sheet with styled fields."""
    ws = wb.active
    ws.title = "Project Summary"

    # Header styling
    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
    thin_border = Border(
        bottom=Side(style="thin", color="e2e8f0")
    )

    # Column headers
    headers = ["Field", "Value", "Confidence", "Source", "Page", "Requires Review"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="left")

    # Field labels (human-readable)
    field_labels = {
        "project_name": "Project Name",
        "project_owner": "Project Owner",
        "location": "Location",
        "submission_deadline": "Submission Deadline",
        "bid_validity_period": "Bid Validity Period",
        "pre_bid_meeting_date": "Pre-Bid Meeting Date",
        "scope_of_work": "Scope of Work",
        "contract_type": "Contract Type",
        "tender_bond": "Tender Bond",
        "advance_payment": "Advance Payment",
        "retention_percentage": "Retention Percentage",
        "payment_terms": "Payment Terms",
        "stakeholders": "Stakeholders",
    }

    row = 2
    for field_key, label in field_labels.items():
        field = summary_data.get(field_key, {})
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=field.get("value", ""))
        ws.cell(row=row, column=3, value=field.get("confidence_level", ""))
        citations = field.get("citations", [])
        if citations:
            ws.cell(row=row, column=4, value=citations[0].get("document_name", ""))
            ws.cell(row=row, column=5, value=citations[0].get("page_number", ""))
        ws.cell(row=row, column=6, value="Yes" if field.get("requires_review") else "No")
        row += 1

    # Auto-width columns
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
```

### PDF Report with WeasyPrint + Jinja2
```python
# Source: WeasyPrint docs + project architecture
from io import BytesIO
from pathlib import Path
import weasyprint
from jinja2 import Environment, FileSystemLoader

def generate_pdf_report(
    project_name: str,
    summary_data: dict,
    checklist_data: dict,
) -> BytesIO:
    """Generate a formatted PDF report with summary, checklist, and citations."""
    templates_dir = Path(__file__).parent.parent.parent / "templates" / "reports"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("pdf_report.html")

    html_string = template.render(
        project_name=project_name,
        summary=summary_data,
        checklist=checklist_data,
    )

    # CSS for the PDF (can reference external stylesheets too)
    css_path = Path(__file__).parent.parent.parent / "static" / "css" / "pdf_report.css"

    html = weasyprint.HTML(string=html_string)
    stylesheets = []
    if css_path.exists():
        stylesheets.append(weasyprint.CSS(filename=str(css_path)))

    buffer = BytesIO()
    html.write_pdf(buffer, stylesheets=stylesheets)
    buffer.seek(0)
    return buffer
```

### PDF Report HTML Template (Jinja2)
```html
<!-- Source: WeasyPrint + project schema analysis -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 2cm;
            @bottom-center { content: "Page " counter(page) " of " counter(pages); }
        }
        body { font-family: 'Noto Sans', 'Noto Sans Arabic', sans-serif; font-size: 10pt; }
        .rtl { direction: rtl; text-align: right; }
        h1 { font-size: 18pt; color: #1a1a2e; }
        .field-table { width: 100%; border-collapse: collapse; margin-bottom: 1em; }
        .field-table th, .field-table td { padding: 6px 8px; border: 1px solid #e2e8f0; }
        .field-table th { background: #f8fafc; font-weight: 600; text-align: left; }
        .confidence-high { color: #16a34a; }
        .confidence-medium { color: #d97706; }
        .confidence-low { color: #dc2626; }
        .citation-appendix { page-break-before: always; }
    </style>
</head>
<body>
    <h1>{{ project_name }} - Tender Analysis Report</h1>

    <h2>Project Summary</h2>
    <table class="field-table">
        <tr><th>Field</th><th>Value</th><th>Confidence</th></tr>
        {% for field_name, field in summary.items() %}
        <tr>
            <td>{{ field_name | replace('_', ' ') | title }}</td>
            <td>{{ field.value or 'Not found' }}</td>
            <td class="confidence-{{ field.confidence_level }}">{{ field.confidence_level }}</td>
        </tr>
        {% endfor %}
    </table>

    <!-- Citation appendix -->
    <div class="citation-appendix">
        <h2>Citation Appendix</h2>
        {% for field_name, field in summary.items() %}
            {% for citation in field.citations %}
            <p><strong>{{ field_name | replace('_', ' ') | title }}:</strong>
               {{ citation.document_name }}, p.{{ citation.page_number }}:
               <em>"{{ citation.quote }}"</em></p>
            {% endfor %}
        {% endfor %}
    </div>
</body>
</html>
```

### PATCH Endpoint for Checklist Item Updates
```python
# Source: FastAPI docs + SQLAlchemy patterns
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified
from app.database import async_session_factory
from app.models.project import Project

class ChecklistItemUpdate(BaseModel):
    category: str  # "requirements", "submission_documents", or "eligibility_criteria"
    index: int     # Item index within the category list
    updates: dict  # Fields to update (e.g., {"checked": true} or {"requirement": "new text"})

@router.patch("/projects/{project_id}/checklist/items")
async def update_checklist_item(project_id: int, update: ChecklistItemUpdate):
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if not project or not project.checklist_json:
            raise HTTPException(status_code=404, detail="Checklist not found")

        checklist_data = json.loads(project.checklist_json)
        category_items = checklist_data.get(update.category, [])

        if update.index < 0 or update.index >= len(category_items):
            raise HTTPException(status_code=400, detail="Invalid item index")

        # Apply updates to the specific item
        category_items[update.index].update(update.updates)

        # Re-serialize and persist
        project.checklist_json = json.dumps(checklist_data, ensure_ascii=False)
        flag_modified(project, "checklist_json")
        await session.commit()

        return {"status": "updated", "category": update.category, "index": update.index}
```

### FastAPI Export Endpoint
```python
# Source: FastAPI docs (custom-response)
from io import BytesIO
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

@router.get("/projects/{project_id}/export/excel")
async def export_project_excel(project_id: int):
    # Load project data (summary + checklist)
    buffer = await generate_excel_report(project_id)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="project_{project_id}_report.xlsx"'
        },
    )

@router.get("/projects/{project_id}/export/pdf")
async def export_project_pdf(project_id: int):
    buffer = await generate_pdf_report(project_id)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="project_{project_id}_report.pdf"'
        },
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| xhtml2pdf for HTML-to-PDF | WeasyPrint 68.x | WeasyPrint mature since v50+, RTL fix in v65 | Better CSS support, RTL Arabic works, active maintenance |
| fpdf/pyfpdf for PDF gen | fpdf2 with text shaping | fpdf2 fork active since 2020 | RTL support via uharfbuzz, but multi-line bug remains |
| wkhtmltopdf for PDF | WeasyPrint (no external binary) | 2023+ (wkhtmltopdf abandoned) | No need for headless browser or external binary |
| ReportLab for Arabic PDF | ReportLab 4.4+ with initial RTL | April 2025 | Initial support only; WeasyPrint is more mature for RTL |

**Deprecated/outdated:**
- wkhtmltopdf: Abandoned project, no longer maintained. Do not use PDFKit wrapper.
- pyfpdf (original): Replaced by fpdf2 fork. Original repo archived.
- xhtml2pdf RTL: Experimental, incomplete. Not production-ready for Arabic.

## Open Questions

1. **Arabic font bundling**
   - What we know: WeasyPrint needs a font with Arabic glyph coverage referenced via CSS @font-face
   - What's unclear: Which specific font to bundle (Noto Sans Arabic, Amiri, Cairo). File size impact.
   - Recommendation: Use Noto Sans Arabic (Google Fonts, free, good coverage). Download .ttf and place in app/static/fonts/. ~300KB. Test with actual Arabic tender document content.

2. **WeasyPrint on Windows developer machines**
   - What we know: Requires MSYS2 + Pango. More complex than Linux/macOS.
   - What's unclear: Whether all developers have MSYS2 set up. Whether there are PATH issues.
   - Recommendation: Document setup steps clearly. Consider making PDF export a "soft" feature that degrades gracefully if WeasyPrint is not installed (try/except on import, disable export button).

3. **Checklist "checked" field not in current schema**
   - What we know: VerifiedRequirement schema has requirement, description, category, is_mandatory, citation, confidence, requires_review. There is no "checked" or "completed" boolean.
   - What's unclear: Whether to add a "checked" field to the Pydantic schema or track it separately.
   - Recommendation: Add a `checked: bool = False` field to the checklist JSON data structure. When the PATCH endpoint updates an item, it adds/modifies this field. The Pydantic schema should be extended with this optional field.

## Sources

### Primary (HIGH confidence)
- openpyxl 3.1.x stable docs (https://openpyxl.readthedocs.io/en/stable/styles.html) - styling API, cell formatting
- FastAPI custom response docs (https://fastapi.tiangolo.com/advanced/custom-response/) - StreamingResponse, FileResponse
- WeasyPrint 68.1 first steps (https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) - installation, dependencies
- Existing codebase analysis - all API endpoints, schemas, templates, models verified by reading source files

### Secondary (MEDIUM confidence)
- WeasyPrint RTL fix PR #2404 / Issue #1686 (https://github.com/Kozea/WeasyPrint/issues/1686) - RTL duplicate text fixed in v65+
- fpdf2 text shaping docs (https://py-pdf.github.io/fpdf2/TextShaping.html) - RTL support details and known limitations
- fpdf2 RTL multi-line bug (https://github.com/py-pdf/fpdf2/issues/901) - lines render bottom-to-top, unresolved
- FastAPI body updates docs (https://fastapi.tiangolo.com/tutorial/body-updates/) - PATCH pattern with exclude_unset

### Tertiary (LOW confidence)
- WeasyPrint Windows installation complexity - based on web search reports and GitHub issues; should be validated on actual dev machines

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - openpyxl already in project; WeasyPrint well-documented with verified RTL fix
- Architecture: HIGH - extends established patterns (Jinja2 SSR, fetch + DOM, FastAPI routing) already in codebase
- Pitfalls: HIGH - based on documented issues (SQLAlchemy flag_modified, WeasyPrint system deps, font embedding) with verified sources
- Export patterns: HIGH - openpyxl BytesIO + StreamingResponse is the canonical FastAPI pattern; WeasyPrint Jinja2 integration well-documented
- Checklist editing: MEDIUM - PATCH endpoint pattern is standard, but the "checked" field addition needs validation against existing data

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days - all libraries are stable releases)
