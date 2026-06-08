# Phase 7A — Additional Document Parsers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand ingestion beyond PDF/DOCX/XLSX by adding TXT, EML, MSG, PPTX, image (OCR, graceful), and ZIP (recursive) parsers, all implementing the root app's `ParserInterface` and wired into `get_parser_for_file` + the upload allow-list.

**Architecture:** Each new parser subclasses `app/services/parsing/base.ParserInterface`, returns the uniform `ParsedDocument` (filename, content_type, full_text, pages[PageContent], tables, metadata, page_count, processing_time_ms, warnings). Heavy/optional deps (python-pptx, extract-msg, OCR engines) are lazily imported inside `parse()` and degrade gracefully (a warning + empty text) when unavailable, never crashing ingestion. The ZIP parser extracts members to a temp dir and recursively delegates to `get_parser_for_file`, aggregating member pages. Parsers are registered in `get_parser_for_file` and the extension allow-list is widened in `app/api/documents.py`.

**Tech Stack:** Python 3.11, stdlib (email, zipfile), python-pptx, extract-msg, Pillow + (easyocr or pytesseract) for OCR, pytest.

**Source extraction logic to adapt (read each):** `bidops-ai/backend/app/parsers/{email_parser,pptx_parser,image_parser}.py`. These contain working extraction code on a *different* base class (`ParsedContent`); reuse their extraction logic but return the root app's `ParsedDocument`/`PageContent` shape instead.

**Decomposition note:** Plan **7A** of Phase 7 (Ingestion expansion). Siblings (separate plans): **7B** BOQ Excel parsing + trade classification, **7C** document classification + addenda-supersedes versioning. XER/CAD engineering parsers are a later slice (need ezdxf + ODA converter).

---

## File Structure

- `app/services/parsing/text_parser.py` — CREATE: `TextParser` (.txt, .md, .csv).
- `app/services/parsing/email_parser.py` — CREATE: `EmailParser` (.eml stdlib; .msg via extract-msg, graceful).
- `app/services/parsing/pptx_parser.py` — CREATE: `PptxParser` (.pptx via python-pptx).
- `app/services/parsing/image_parser.py` — CREATE: `ImageParser` (.png/.jpg/.jpeg/.tiff/.bmp; OCR graceful).
- `app/services/parsing/zip_parser.py` — CREATE: `ZipParser` (.zip; recursive via get_parser_for_file).
- `app/services/parsing/base.py` — MODIFY: register new parsers in `get_parser_for_file` (keep lazy imports).
- `app/api/documents.py` — MODIFY: widen `ALLOWED_EXTENSIONS`.
- `requirements.txt` — MODIFY: add `python-pptx`, `extract-msg`, `Pillow`.
- `tests/parsing/__init__.py`, `tests/parsing/test_*.py` — CREATE: one test module per parser (generate fixtures in-test).

---

## Task 1: Dependencies

**Files:** Modify `requirements.txt`

- [ ] **Step 1: Add deps to the venv**

Run: `.venv/Scripts/python.exe -m pip install python-pptx extract-msg Pillow`
Expected: installs successfully (Pillow may already be present via docling/easyocr).

- [ ] **Step 2: Append to `requirements.txt`** (under the "Document parsing" section)

```
# Additional document formats (Phase 7A)
python-pptx
extract-msg
Pillow
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build(parsers): add python-pptx, extract-msg, Pillow for Phase 7A formats"
```

---

## Task 2: `TextParser` (.txt, .md, .csv)

**Files:** Create `app/services/parsing/text_parser.py`; Test `tests/parsing/__init__.py` (empty) + `tests/parsing/test_text_parser.py`

- [ ] **Step 1: Write the failing test `tests/parsing/test_text_parser.py`**

```python
import pytest


async def test_text_parser_reads_plain_text(tmp_path):
    from app.services.parsing.text_parser import TextParser

    f = tmp_path / "note.txt"
    f.write_text("Tender deadline: 20 April 2026.\nBond: 5,000,000.", encoding="utf-8")

    parsed = await TextParser().parse(str(f))
    assert parsed.content_type == "txt"
    assert "Tender deadline" in parsed.full_text
    assert parsed.page_count == 1
    assert parsed.pages[0].page_number == 1
    assert "Bond" in parsed.pages[0].text


def test_text_parser_supports_extensions():
    from app.services.parsing.text_parser import TextParser

    p = TextParser()
    assert p.can_parse("a.txt") and p.can_parse("b.md") and p.can_parse("c.csv")
    assert not p.can_parse("d.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_text_parser.py -v`
Expected: FAIL (ModuleNotFoundError). Create `tests/parsing/__init__.py` (empty) first.

- [ ] **Step 3: Create `app/services/parsing/text_parser.py`**

```python
"""Plain-text / markdown / CSV parser implementing ParserInterface."""

from __future__ import annotations

import time
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface


class TextParser(ParserInterface):
    """Parses UTF-8 (BOM/latin-1 fallback) plain-text files into one page."""

    supported_extensions = [".txt", ".md", ".csv"]

    async def parse(self, file_path: str) -> ParsedDocument:
        start = time.monotonic()
        warnings: list[str] = []
        path = Path(file_path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1", errors="replace")
            warnings.append("Decoded with latin-1 fallback (non-UTF-8 content).")

        elapsed = int((time.monotonic() - start) * 1000)
        return ParsedDocument(
            filename=path.name,
            content_type="txt",
            full_text=text,
            pages=[PageContent(page_number=1, text=text, tables=[])],
            tables=[],
            metadata={"char_count": len(text)},
            page_count=1,
            processing_time_ms=elapsed,
            warnings=warnings,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_text_parser.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/parsing/text_parser.py tests/parsing/__init__.py tests/parsing/test_text_parser.py
git commit -m "feat(parsers): TextParser for .txt/.md/.csv"
```

---

## Task 3: `EmailParser` (.eml stdlib, .msg graceful)

**Files:** Create `app/services/parsing/email_parser.py`; Test `tests/parsing/test_email_parser.py`

- [ ] **Step 1: Write the failing test `tests/parsing/test_email_parser.py`**

```python
async def test_email_parser_reads_eml(tmp_path):
    from email.message import EmailMessage
    from app.services.parsing.email_parser import EmailParser

    msg = EmailMessage()
    msg["Subject"] = "RFQ - Concrete Package"
    msg["From"] = "buyer@acme.test"
    msg["To"] = "sales@supplier.test"
    msg.set_content("Please quote the attached BOQ. Deadline 20 April.")

    f = tmp_path / "mail.eml"
    f.write_bytes(bytes(msg))

    parsed = await EmailParser().parse(str(f))
    assert parsed.content_type == "eml"
    assert "RFQ - Concrete Package" in parsed.full_text
    assert "buyer@acme.test" in parsed.full_text
    assert "Please quote" in parsed.full_text
    assert parsed.metadata.get("subject") == "RFQ - Concrete Package"


def test_email_parser_extensions():
    from app.services.parsing.email_parser import EmailParser
    p = EmailParser()
    assert p.can_parse("x.eml") and p.can_parse("y.msg")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_email_parser.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/services/parsing/email_parser.py`**

Implement `EmailParser(ParserInterface)` with `supported_extensions = [".eml", ".msg"]`. Adapt extraction logic from `bidops-ai/backend/app/parsers/email_parser.py` but return the root `ParsedDocument`:
- `.eml`: parse with stdlib `email.parser.BytesParser(policy=email.policy.default)`. Build a header block (`Subject`, `From`, `To`, `Cc`, `Date`) + the plain-text body (prefer `text/plain`, else strip the `text/html` part). Collect attachment filenames into `metadata["attachments"]`.
- `.msg`: lazily `import extract_msg` inside `parse()`; on `ImportError`, return a `ParsedDocument` with `warnings=["extract-msg not installed; .msg body not extracted"]`, empty `full_text`, and `metadata` with whatever is available — do NOT raise. Otherwise extract sender/to/cc/subject/date/body.
- `full_text` = header block + "\n\n" + body. `pages` = one `PageContent(page_number=1, text=full_text)`. `content_type` = "eml" or "msg" by extension. Set `metadata["subject"]`, `["from"]`, `["to"]`, `["attachments"]`. Wrap any unexpected error so the parser returns a `ParsedDocument` with a warning rather than raising (parsers signal failure via empty text + warnings, per `document_service` convention).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_email_parser.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/parsing/email_parser.py tests/parsing/test_email_parser.py
git commit -m "feat(parsers): EmailParser (.eml stdlib, .msg graceful via extract-msg)"
```

---

## Task 4: `PptxParser` (.pptx)

**Files:** Create `app/services/parsing/pptx_parser.py`; Test `tests/parsing/test_pptx_parser.py`

- [ ] **Step 1: Write the failing test `tests/parsing/test_pptx_parser.py`**

```python
async def test_pptx_parser_extracts_slide_text(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches
    from app.services.parsing.pptx_parser import PptxParser

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    box.text_frame.text = "Project Kickoff - New Cairo Medical Center"
    f = tmp_path / "deck.pptx"
    prs.save(str(f))

    parsed = await PptxParser().parse(str(f))
    assert parsed.content_type == "pptx"
    assert "New Cairo Medical Center" in parsed.full_text
    assert parsed.page_count == 1
    assert parsed.pages[0].page_number == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_pptx_parser.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/services/parsing/pptx_parser.py`**

Implement `PptxParser(ParserInterface)`, `supported_extensions = [".pptx"]`. Adapt from `bidops-ai/backend/app/parsers/pptx_parser.py`:
- Lazily `from pptx import Presentation` inside `parse()`; on ImportError return graceful warning ParsedDocument.
- One `PageContent` per slide (page_number = slide index, 1-based): concatenate each shape's `shape.text`; extract tables (`shape.has_table`) into the page's `tables` as `{"headers":[...],"data":[[...]],"rows":r,"cols":c}` (first row = headers); include speaker notes if present.
- `full_text` = all slide texts joined by `"\n\n"`. `metadata` = core_properties (title/author) + `slide_count`. `page_count` = number of slides. `content_type="pptx"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_pptx_parser.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/parsing/pptx_parser.py tests/parsing/test_pptx_parser.py
git commit -m "feat(parsers): PptxParser for .pptx (text, tables, notes)"
```

---

## Task 5: `ImageParser` (.png/.jpg/.jpeg/.tiff/.bmp, OCR graceful)

**Files:** Create `app/services/parsing/image_parser.py`; Test `tests/parsing/test_image_parser.py`

- [ ] **Step 1: Write the failing test `tests/parsing/test_image_parser.py`**

```python
async def test_image_parser_returns_metadata_and_degrades_gracefully(tmp_path):
    from PIL import Image
    from app.services.parsing.image_parser import ImageParser

    img = Image.new("RGB", (120, 40), color="white")
    f = tmp_path / "scan.png"
    img.save(str(f))

    parsed = await ImageParser().parse(str(f))
    assert parsed.content_type == "image"
    assert parsed.page_count == 1
    assert parsed.metadata.get("width") == 120 and parsed.metadata.get("height") == 40
    # OCR may be unavailable in this env -> must NOT raise; full_text is str,
    # and if no OCR engine, a warning is recorded.
    assert isinstance(parsed.full_text, str)
    if not parsed.full_text.strip():
        assert any("ocr" in w.lower() for w in parsed.warnings)


def test_image_parser_extensions():
    from app.services.parsing.image_parser import ImageParser
    p = ImageParser()
    for ext in ("a.png", "b.jpg", "c.jpeg", "d.tiff", "e.bmp"):
        assert p.can_parse(ext)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_image_parser.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/services/parsing/image_parser.py`**

Implement `ImageParser(ParserInterface)`, `supported_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]`:
- `from PIL import Image` (Pillow); open the image, record `metadata` = width/height/mode/format.
- OCR with graceful fallback chain, each in try/except, appending a warning on failure:
  1. Try EasyOCR: `import easyocr; reader = easyocr.Reader(["en", "ar"], gpu=False); text = "\n".join(reader.readtext(file_path, detail=0))`.
  2. If EasyOCR import/run fails, try `import pytesseract; text = pytesseract.image_to_string(img, lang="eng+ara")`.
  3. If both fail, `text = ""` and append `warnings=["OCR unavailable (easyocr/pytesseract not usable in this environment); image text not extracted."]`.
- `full_text` = OCR text (or ""). `pages` = one `PageContent(page_number=1, text=full_text)`. `content_type="image"`. `page_count=1`. Never raise on OCR failure.

Note: EasyOCR currently fails to import in this environment (python-bidi 0.4.2 vs easyocr's `from bidi import get_display`); the graceful chain handles that — the test asserts graceful degradation, not successful OCR.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_image_parser.py -v`
Expected: PASS (graceful path).

- [ ] **Step 5: Commit**

```bash
git add app/services/parsing/image_parser.py tests/parsing/test_image_parser.py
git commit -m "feat(parsers): ImageParser with graceful OCR (easyocr->pytesseract->skip)"
```

---

## Task 6: `ZipParser` (.zip, recursive)

**Files:** Create `app/services/parsing/zip_parser.py`; Test `tests/parsing/test_zip_parser.py`

- [ ] **Step 1: Write the failing test `tests/parsing/test_zip_parser.py`**

```python
import zipfile


async def test_zip_parser_aggregates_supported_members(tmp_path):
    from app.services.parsing.zip_parser import ZipParser

    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "Alpha tender note")
        zf.writestr("b.md", "# Beta spec section")
        zf.writestr("ignore.xyz", "unsupported binary")

    parsed = await ZipParser().parse(str(z))
    assert parsed.content_type == "zip"
    assert "Alpha tender note" in parsed.full_text
    assert "Beta spec section" in parsed.full_text
    # two supported members -> two pages; unsupported member noted in warnings
    assert parsed.page_count == 2
    assert any("ignore.xyz" in w for w in parsed.warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_zip_parser.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/services/parsing/zip_parser.py`**

```python
"""ZIP archive parser: extracts members and recursively parses supported files."""

from __future__ import annotations

import tempfile
import time
import zipfile
from pathlib import Path

from app.services.parsing.base import (
    PageContent,
    ParsedDocument,
    ParserInterface,
    get_parser_for_file,
)


class ZipParser(ParserInterface):
    """Extracts a .zip and aggregates parsed text from supported members.

    Each supported member becomes one page (labelled with its archive path).
    Unsupported members and per-member parse failures are recorded as warnings,
    never raised, so a partially-parseable archive still ingests.
    """

    supported_extensions = [".zip"]

    async def parse(self, file_path: str) -> ParsedDocument:
        start = time.monotonic()
        warnings: list[str] = []
        pages: list[PageContent] = []
        tables: list[dict] = []
        texts: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            try:
                with zipfile.ZipFile(file_path) as zf:
                    members = [m for m in zf.namelist() if not m.endswith("/")]
                    for member in members:
                        try:
                            parser = get_parser_for_file(member)
                        except ValueError:
                            warnings.append(f"Skipped unsupported member: {member}")
                            continue
                        extracted = Path(zf.extract(member, tmp))
                        try:
                            sub = await parser.parse(str(extracted))
                        except Exception as exc:  # noqa: BLE001
                            warnings.append(f"Failed to parse member {member}: {exc}")
                            continue
                        page_no = len(pages) + 1
                        label = f"[{member}]\n{sub.full_text}"
                        pages.append(PageContent(page_number=page_no, text=label))
                        texts.append(label)
                        for t in sub.tables:
                            tables.append({**t, "source_member": member})
                        warnings.extend(f"{member}: {w}" for w in sub.warnings)
            except zipfile.BadZipFile:
                warnings.append("Invalid or corrupt ZIP archive.")

        elapsed = int((time.monotonic() - start) * 1000)
        return ParsedDocument(
            filename=Path(file_path).name,
            content_type="zip",
            full_text="\n\n".join(texts),
            pages=pages,
            tables=tables,
            metadata={"member_count": len(pages)},
            page_count=len(pages),
            processing_time_ms=elapsed,
            warnings=warnings,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_zip_parser.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/parsing/zip_parser.py tests/parsing/test_zip_parser.py
git commit -m "feat(parsers): ZipParser (recursive member extraction + aggregation)"
```

---

## Task 7: Register parsers + widen the upload allow-list

**Files:** Modify `app/services/parsing/base.py`, `app/api/documents.py`; Test `tests/parsing/test_registry.py`

- [ ] **Step 1: Write the failing test `tests/parsing/test_registry.py`**

```python
import pytest


@pytest.mark.parametrize(
    "filename,expected_cls",
    [
        ("a.txt", "TextParser"), ("a.md", "TextParser"), ("a.csv", "TextParser"),
        ("a.eml", "EmailParser"), ("a.msg", "EmailParser"),
        ("a.pptx", "PptxParser"),
        ("a.png", "ImageParser"), ("a.jpg", "ImageParser"),
        ("a.zip", "ZipParser"),
        ("a.pdf", "PdfParser"), ("a.docx", "DocxParser"), ("a.xlsx", "XlsxParser"),
    ],
)
def test_registry_routes_extension(filename, expected_cls):
    from app.services.parsing.base import get_parser_for_file
    assert type(get_parser_for_file(filename)).__name__ == expected_cls


def test_upload_allowlist_includes_new_formats():
    from app.api.documents import ALLOWED_EXTENSIONS
    for ext in (".txt", ".md", ".csv", ".eml", ".msg", ".pptx",
                ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".zip"):
        assert ext in ALLOWED_EXTENSIONS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_registry.py -v`
Expected: FAIL (new parsers not registered / extensions not allowed).

- [ ] **Step 3: Register parsers in `get_parser_for_file` (`app/services/parsing/base.py`)**

Extend the lazy import block and `parsers` list (keep existing PDF/DOCX/XLSX first so their extensions keep priority):

```python
    from app.services.parsing.pdf_parser import PdfParser
    from app.services.parsing.docx_parser import DocxParser
    from app.services.parsing.xlsx_parser import XlsxParser
    from app.services.parsing.text_parser import TextParser
    from app.services.parsing.email_parser import EmailParser
    from app.services.parsing.pptx_parser import PptxParser
    from app.services.parsing.image_parser import ImageParser
    from app.services.parsing.zip_parser import ZipParser

    parsers: list[ParserInterface] = [
        PdfParser(),
        DocxParser(),
        XlsxParser(),
        TextParser(),
        EmailParser(),
        PptxParser(),
        ImageParser(),
        ZipParser(),
    ]
```

- [ ] **Step 4: Widen `ALLOWED_EXTENSIONS` in `app/api/documents.py`**

```python
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls",
    ".txt", ".md", ".csv",
    ".eml", ".msg",
    ".pptx",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp",
    ".zip",
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/parsing/test_registry.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/parsing/base.py app/api/documents.py tests/parsing/test_registry.py
git commit -m "feat(parsers): register new parsers + widen upload allow-list"
```

---

## Task 8: Full-suite check

- [ ] **Step 1: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS (Phase 6A/6B + 7A parser tests). Report the count.

- [ ] **Step 2: Boot smoke**

Run: `.venv/Scripts/python.exe -c "import app.main; from app.services.parsing.base import get_parser_for_file; print('zip ->', type(get_parser_for_file('x.zip')).__name__)"`
Expected: prints `zip -> ZipParser`; no import errors.

- [ ] **Step 3: Commit** (only if anything was adjusted in this task — otherwise skip)

---

## Self-Review (completed by author)

- **Spec coverage:** Implements the "additional document parsers" portion of Phase 7 ingestion expansion: TXT/MD/CSV, EML/MSG, PPTX, image (OCR-graceful), ZIP (recursive). All implement the root `ParserInterface` and return `ParsedDocument`, so the existing `document_service` ingest/index pipeline consumes them unchanged. Registered in `get_parser_for_file`; upload allow-list widened.
- **Out of scope (sibling plans):** XER/CAD engineering parsers (need ezdxf + ODA converter), BOQ Excel parsing/classification (7B), document classification + addenda versioning (7C).
- **Placeholder scan:** Full code for TextParser and ZipParser (new logic) + all test code + registry/allow-list edits are inline. EmailParser/PptxParser/ImageParser specify exact interface, extensions, fields, graceful-degradation behavior, and the source file to adapt extraction logic from — actionable adaptation, not placeholders.
- **Type consistency:** Every parser returns `ParsedDocument(filename, content_type, full_text, pages=[PageContent], tables, metadata, page_count, processing_time_ms, warnings)` matching `base.py`. `content_type` values: txt/eml/msg/pptx/image/zip. Registry test enumerates each extension→class.
- **Graceful degradation:** OCR (easyocr/pytesseract) and .msg (extract-msg) failures produce warnings + empty text, never exceptions — matching `document_service`'s "parsers signal failure via warnings" convention, so a missing optional dep/binary never breaks ingestion.
- **Test isolation:** every test generates its own fixture under `tmp_path`; no external sample files or binaries required (image/MSG tests assert graceful behavior, not successful OCR/MSG extraction).
