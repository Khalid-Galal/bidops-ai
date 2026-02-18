# Phase 1: Document Ingestion Pipeline - Research

**Researched:** 2026-02-18
**Domain:** Document parsing (PDF/DOCX/XLSX), FastAPI application scaffold, file upload, background processing
**Confidence:** HIGH

## Summary

Phase 1 builds the foundational document ingestion pipeline for BidOps AI. It requires: (1) a FastAPI application scaffold with SQLite database, project model, and file upload API; (2) a multi-format document parsing pipeline handling PDF (with OCR fallback), DOCX, and XLSX; and (3) a folder batch upload mechanism with progress tracking and a minimal web upload UI.

The standard approach is a FastAPI backend using async SQLAlchemy 2.0 with aiosqlite for SQLite, Alembic for migrations, and Pydantic v2 for request/response validation. Document parsing uses Docling as the primary unified parser for PDF and DOCX (with its built-in table structure recognition and OCR support), supplemented by openpyxl for XLSX since Docling's Excel support has known edge cases. Background processing uses asyncio tasks with SSE (Server-Sent Events) for real-time progress streaming to the browser. The web UI is a minimal Jinja2-templated HTML interface served directly from FastAPI, avoiding the complexity of a React SPA for v1.

**Primary recommendation:** Use Docling as the unified parser for PDF and DOCX with its native table/structure extraction and OCR, use openpyxl directly for XLSX (more reliable than Docling's XLSX support), and serve a minimal Jinja2 HTML upload interface from FastAPI with SSE-based progress streaming.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-05 | System runs as local FastAPI backend with browser-based UI | FastAPI 0.115+ scaffold with Jinja2 templates served via StaticFiles, Uvicorn ASGI server on localhost:8000 |
| UI-01 | User can create projects and upload documents via web interface | FastAPI CRUD endpoints for projects + multi-file UploadFile endpoint + Jinja2 HTML templates |
| ING-01 | User can upload and parse PDF documents including scanned PDFs via OCR | Docling DocumentConverter with PdfPipelineOptions (do_ocr=True, EasyOcrOptions for Arabic/English) |
| ING-02 | User can upload and parse Word (DOCX) documents | Docling DocumentConverter with InputFormat.DOCX support (native DOCX parsing) |
| ING-03 | User can upload and parse Excel (XLSX) files (BOQ, pricing sheets) | openpyxl with data_only=True and read_only=True for reliable sheet/table extraction |
| ING-04 | User can batch upload an entire folder of documents at once | FastAPI endpoint accepting list[UploadFile] with folder simulation, recursive file discovery |
| ING-05 | User sees progress indication during document processing | SSE (Server-Sent Events) via sse-starlette with asyncio task queue for real-time progress |
| LANG-02 | System handles English text correctly | Docling's default text extraction handles English natively; openpyxl preserves text as-is |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | REST API backend + HTML serving | Async-first, native UploadFile, Jinja2 template support, automatic OpenAPI docs |
| Uvicorn | latest | ASGI server | FastAPI's recommended server, included in `fastapi[standard]` |
| SQLAlchemy | 2.0+ | ORM and database access | Async support via create_async_engine, mapped_column syntax, mature migrations via Alembic |
| aiosqlite | 0.20+ | Async SQLite driver | Asyncio bridge to sqlite3, compatible with SQLAlchemy async engine on Windows |
| Alembic | 1.14+ | Database migrations | Official SQLAlchemy migration tool, supports async with `--template async` |
| Pydantic | 2.x | Request/response validation | Native FastAPI integration, model_validate for ORM objects, JSON schema generation |
| Docling | 2.72+ | PDF and DOCX parsing | IBM's unified parser: 97.9% table accuracy, built-in OCR, page metadata, structure preservation |
| openpyxl | 3.1+ | XLSX parsing | Reliable Excel reading with data_only mode, merged cell handling, sheet metadata |
| python-multipart | latest | File upload support | Required by FastAPI for UploadFile/Form handling |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | 2.0+ | Server-Sent Events | Real-time progress streaming to browser during document processing |
| Jinja2 | 3.1+ | HTML templates | Serving minimal upload UI pages from FastAPI |
| aiofiles | latest | Async file I/O | Writing uploaded files to disk asynchronously |
| pydantic-settings | 2.x | Configuration management | Loading settings from .env file (DB path, upload dir, etc.) |
| python-magic-bin | latest | File type validation | Validate uploads by magic bytes on Windows (not just extension) |
| EasyOCR | 1.7+ | Arabic/English OCR | Used via Docling's EasyOcrOptions for scanned PDF OCR |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Docling for PDF | PyMuPDF (fitz) | Simpler/faster but no table structure recognition, manual OCR integration needed |
| Docling for DOCX | python-docx directly | Lower-level, more control but no unified output format with PDF parsing |
| openpyxl for XLSX | Docling InputFormat.XLSX | Docling XLSX has known edge cases (sheet selection, IndexError with some options); openpyxl is battle-tested |
| Jinja2 HTML UI | React SPA | Full React SPA is overkill for Phase 1 minimal upload interface; can migrate later |
| SSE for progress | WebSocket | WebSocket is bidirectional (overkill); SSE is simpler one-way server-to-client push |
| SSE for progress | Polling /status endpoint | Polling adds latency and unnecessary requests; SSE is more efficient |
| asyncio tasks | Celery | Celery requires Redis/RabbitMQ broker; overkill for single-user local app |

**Installation:**
```bash
# Create virtual environment (Python 3.11+ recommended)
python -m venv venv
venv\Scripts\activate  # Windows

# Core framework
pip install "fastapi[standard]" uvicorn

# Database
pip install sqlalchemy[asyncio] aiosqlite alembic

# Document parsing
pip install docling openpyxl

# OCR support (installed via Docling, but ensure EasyOCR available)
pip install easyocr

# File handling and UI
pip install python-multipart aiofiles python-magic-bin jinja2

# Progress streaming
pip install sse-starlette

# Configuration
pip install pydantic-settings
```

**Note on Docling installation:** Docling pulls in heavy dependencies (PyTorch, transformers). First install may take several minutes and download ~2GB of model files. On Windows, ensure MSVC build tools are available for native extensions.

## Architecture Patterns

### Recommended Project Structure

```
bidops-ai/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app creation, lifespan, router mounting
│   ├── config.py             # pydantic-settings Settings class
│   ├── database.py           # async engine, sessionmaker, get_db dependency
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py           # Base, enums (ProjectStatus, DocumentStatus)
│   │   ├── project.py        # Project model
│   │   └── document.py       # Document model (stores parsed content metadata)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── project.py        # ProjectCreate, ProjectResponse, etc.
│   │   └── document.py       # DocumentResponse, UploadResponse, ProgressEvent
│   ├── api/
│   │   ├── __init__.py
│   │   ├── projects.py       # Project CRUD endpoints
│   │   ├── documents.py      # Upload, list, progress endpoints
│   │   └── health.py         # Health check
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_service.py   # Orchestrates parsing pipeline
│   │   └── parsing/
│   │       ├── __init__.py
│   │       ├── base.py           # ParsedDocument dataclass, ParserInterface
│   │       ├── pdf_parser.py     # Docling-based PDF parser
│   │       ├── docx_parser.py    # Docling-based DOCX parser
│   │       └── xlsx_parser.py    # openpyxl-based XLSX parser
│   └── templates/
│       ├── base.html             # Base HTML layout
│       ├── index.html            # Project list / home page
│       ├── project.html          # Project detail with upload area
│       └── upload.html           # File upload with progress display
├── migrations/
│   ├── env.py                # Alembic async env
│   ├── script.py.mako
│   └── versions/
├── data/
│   ├── bidops.db             # SQLite database (created at runtime)
│   └── uploads/              # Uploaded document files
├── alembic.ini
├── requirements.txt
└── pyproject.toml
```

### Pattern 1: Async Database Setup with SQLAlchemy 2.0

**What:** Configure async SQLAlchemy engine with aiosqlite and dependency injection for FastAPI.
**When to use:** All database access throughout the application.

```python
# app/database.py
# Source: SQLAlchemy 2.0 async docs + FastAPI integration pattern
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

class Base(DeclarativeBase):
    pass

settings = get_settings()
engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.database_path}",
    echo=settings.debug,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Pattern 2: Parser Registry with Unified Output

**What:** Route files to format-specific parsers that all produce a uniform ParsedDocument output.
**When to use:** When processing uploaded documents of any supported format.

```python
# app/services/parsing/base.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PageContent:
    """Content from a single page/sheet."""
    page_number: int
    text: str
    tables: list[dict] = field(default_factory=list)

@dataclass
class ParsedDocument:
    """Uniform output from all parsers."""
    filename: str
    content_type: str           # "pdf", "docx", "xlsx"
    full_text: str              # Combined text for search/indexing
    pages: list[PageContent]    # Per-page breakdown with text and tables
    tables: list[dict]          # All tables with page numbers
    metadata: dict              # Format-specific metadata
    page_count: int
    processing_time_ms: int
    warnings: list[str] = field(default_factory=list)

class ParserInterface:
    """Interface all parsers implement."""
    supported_extensions: list[str] = []

    def can_parse(self, filename: str) -> bool:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return f".{ext}" in self.supported_extensions

    async def parse(self, file_path: str) -> ParsedDocument:
        raise NotImplementedError
```

### Pattern 3: Background Processing with SSE Progress

**What:** Process documents in asyncio background task, stream progress via Server-Sent Events.
**When to use:** When user uploads documents and needs real-time processing feedback.

```python
# app/api/documents.py (progress streaming pattern)
import asyncio
from fastapi import APIRouter, UploadFile
from sse_starlette.sse import EventSourceResponse

# In-memory progress store (single-user, sufficient for v1)
progress_store: dict[str, dict] = {}

@router.post("/projects/{project_id}/upload")
async def upload_documents(
    project_id: int,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    task_id = str(uuid.uuid4())
    # Save files to disk first
    saved_paths = await save_uploaded_files(files, project_id)
    # Initialize progress
    progress_store[task_id] = {"total": len(saved_paths), "processed": 0, "status": "processing"}
    # Start background processing
    asyncio.create_task(process_documents(task_id, project_id, saved_paths))
    return {"task_id": task_id, "total_files": len(saved_paths)}

@router.get("/progress/{task_id}")
async def stream_progress(task_id: str):
    async def event_generator():
        while True:
            progress = progress_store.get(task_id, {})
            yield {"data": json.dumps(progress)}
            if progress.get("status") in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)
    return EventSourceResponse(event_generator())
```

### Pattern 4: Simplified Project Model (No Auth for v1)

**What:** Project model without user/organization foreign keys since v1 is single-user.
**When to use:** For the v1 project and document data models.

```python
# app/models/project.py
from sqlalchemy import String, Text, Integer, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class ProjectStatus(enum.Enum):
    DRAFT = "draft"
    INGESTING = "ingesting"
    READY = "ready"

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.DRAFT
    )
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    processed_documents: Mapped[int] = mapped_column(Integer, default=0)
    failed_documents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    # No user/org FK - single user for v1
    documents: Mapped[list["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
```

### Pattern 5: FastAPI Lifespan for Initialization

**What:** Use FastAPI lifespan context manager for startup/shutdown tasks.
**When to use:** Application initialization (DB tables, upload directory creation).

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure upload directory exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(title="BidOps AI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
```

### Anti-Patterns to Avoid

- **Synchronous document processing in request thread:** Never parse documents in the API handler. Return task ID immediately, process in asyncio background task. Large PDFs can take 30+ seconds with Docling.
- **Storing parsed text in the API response:** Store parsed content in the database, return only status/metadata to the client.
- **Using Celery for v1:** Celery requires a broker (Redis/RabbitMQ). For single-user local app, asyncio.create_task() is sufficient.
- **Building a React SPA for Phase 1:** Jinja2 templates + vanilla JavaScript is simpler and sufficient for a file upload interface. React can be introduced in Phase 5 if needed.
- **Using sync SQLAlchemy with SQLite:** Always use async (aiosqlite) to avoid blocking the event loop during DB operations.
- **Ignoring Windows path separators:** Always use `pathlib.Path` for file operations. Never hardcode forward or backslashes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction with layout | Custom PyMuPDF extraction | Docling DocumentConverter | Docling preserves reading order, handles multi-column layouts, detects tables automatically |
| PDF table structure recognition | Custom heuristic table detection | Docling's built-in TableFormer | 97.9% accuracy on complex tables including merged cells and multi-page tables |
| OCR for scanned PDFs | Manual pdf2image + pytesseract pipeline | Docling with EasyOcrOptions | Docling integrates OCR into its pipeline, handles mixed text+image pages automatically |
| Database migrations | Manual CREATE TABLE / ALTER TABLE | Alembic autogenerate | Tracks schema changes, supports rollback, generates migration scripts from model diffs |
| File type validation | Extension-only checking | python-magic-bin | Validates by file magic bytes, catches renamed files (e.g., .exe renamed to .pdf) |
| Progress streaming | Custom WebSocket implementation | sse-starlette EventSourceResponse | Standards-based SSE, automatic client disconnect detection, simpler than WebSocket |
| Configuration management | Manual os.environ reading | pydantic-settings BaseSettings | Type validation, .env file loading, nested config, defaults with override |
| Async SQLite access | Custom threading wrapper | aiosqlite via SQLAlchemy async | Battle-tested asyncio bridge, integrates with SQLAlchemy's async engine |

**Key insight:** Document parsing is a deceptively complex domain. PDF is a presentation format (not a data format), so extracting structured content requires sophisticated layout analysis, table detection, and OCR. Docling encapsulates years of IBM research into a single API call. Do not attempt to replicate this with raw PyMuPDF/pdfplumber.

## Common Pitfalls

### Pitfall 1: Docling XLSX Edge Cases
**What goes wrong:** Docling's XLSX/Excel support has known issues -- no sheet selection, IndexError with certain pipeline options (e.g., picture_description enabled), and less mature than PDF/DOCX support.
**Why it happens:** Docling's primary focus is PDF. XLSX support was added later and has fewer edge case fixes.
**How to avoid:** Use openpyxl directly for XLSX parsing. It is battle-tested with decades of Excel support. Use Docling only for PDF and DOCX.
**Warning signs:** Empty tables extracted from XLSX, IndexError during conversion, all sheets parsed when only one is needed.

### Pitfall 2: Docling First-Run Model Download
**What goes wrong:** First invocation of Docling's DocumentConverter downloads ~2GB of model files (layout detection, table structure, OCR models). This blocks the first document parse for several minutes and can fail on slow/restricted networks.
**Why it happens:** Docling uses deep learning models (LayoutParser, TableFormer) that must be downloaded from HuggingFace.
**How to avoid:** Add a startup check / model pre-download step. Document the first-run requirement. Consider caching models in the project's data directory.
**Warning signs:** First parse takes 5+ minutes while subsequent parses are fast. Timeout errors on first run.

### Pitfall 3: UploadFile Read-Once Trap
**What goes wrong:** FastAPI's UploadFile uses SpooledTemporaryFile. Reading the file content once (e.g., for hashing) exhausts the stream, and subsequent reads return empty bytes.
**Why it happens:** SpooledTemporaryFile is a stream, not a buffer. Once read, the position is at the end.
**How to avoid:** Always save the file to disk first using `shutil.copyfileobj(file.file, destination)`, then process from the saved path. Or call `await file.seek(0)` before re-reading.
**Warning signs:** Parsed content is empty despite successful upload. File hash is always the same (hash of empty bytes).

### Pitfall 4: SQLite Async Write Contention
**What goes wrong:** Multiple concurrent background tasks writing to SQLite cause "database is locked" errors. SQLite allows only one writer at a time.
**Why it happens:** aiosqlite uses a background thread per connection, but SQLite's write lock is process-wide.
**How to avoid:** For v1 single-user, process documents sequentially (one at a time in the background task). Use a processing queue, not concurrent tasks. Set `connect_args={"check_same_thread": False}` in engine config.
**Warning signs:** "database is locked" errors during batch upload. Documents marked as failed with no parse errors.

### Pitfall 5: Windows File Path Issues
**What goes wrong:** File paths with backslashes stored in database cause issues when used in web responses or cross-platform code. Long Windows paths (>260 chars) fail.
**Why it happens:** Windows uses backslashes, Python/web use forward slashes. Default Windows path length limit is 260 characters.
**How to avoid:** Always use `pathlib.Path` for file operations. Store paths with forward slashes in the database. Use `str(Path(x).as_posix())` for storage. Enable long paths in Windows if needed.
**Warning signs:** File not found errors with paths that contain backslashes in URLs. Uploads to deeply nested folders fail.

### Pitfall 6: Large File Memory Exhaustion
**What goes wrong:** Reading entire large PDF/XLSX files into memory causes OOM errors. A 100MB PDF with images can expand to 1GB+ in memory during parsing.
**Why it happens:** Some parsing approaches load the entire file into memory. openpyxl without `read_only=True` loads entire workbook.
**How to avoid:** Always use `read_only=True` for openpyxl. Use Docling's `max_file_size` parameter to reject oversized files. Stream file writes with `shutil.copyfileobj` instead of `await file.read()`.
**Warning signs:** Python process memory spikes during upload. Server becomes unresponsive during large file processing.

### Pitfall 7: Missing python-multipart Dependency
**What goes wrong:** FastAPI's UploadFile and Form() fail silently or with cryptic errors if python-multipart is not installed.
**Why it happens:** python-multipart is not a hard dependency of FastAPI but is required for multipart form data.
**How to avoid:** Include python-multipart in requirements.txt. Using `fastapi[standard]` includes it automatically.
**Warning signs:** "No module named 'multipart'" error. Form data returns None.

## Code Examples

### Docling PDF Parsing with OCR and Table Extraction

```python
# Source: Docling official docs + pipeline_options reference
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions, TableStructureOptions
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc.labels import DocItemLabel
import time

def create_pdf_converter() -> DocumentConverter:
    """Create a Docling converter configured for tender documents."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = EasyOcrOptions(
        lang=["en"],  # English for Phase 1; add "ar" in Phase 2
        use_gpu=False,  # Set True if CUDA available
        force_full_page_ocr=False,  # Only OCR pages with insufficient text
    )
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True,
        mode="ACCURATE",  # Use ACCURATE for tender BOQ tables
    )

    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )
    return converter

async def parse_pdf(file_path: str) -> "ParsedDocument":
    """Parse a PDF file using Docling."""
    start = time.time()
    converter = create_pdf_converter()
    result = converter.convert(file_path)
    doc = result.document

    # Extract page-level content
    pages = []
    tables = []

    for item, level in doc.iterate_items():
        label = getattr(item, "label", None)
        text = getattr(item, "text", "").strip()
        prov = item.prov[0] if hasattr(item, "prov") and item.prov else None
        page_no = prov.page_no if prov else None

        if label == DocItemLabel.TABLE:
            # Export table to dataframe
            df = item.export_to_dataframe(doc=doc)
            tables.append({
                "page": page_no,
                "headers": list(df.columns),
                "data": df.values.tolist(),
                "rows": len(df),
                "cols": len(df.columns),
            })

    # Get full markdown text (preserves structure)
    full_text = doc.export_to_markdown()

    processing_time = int((time.time() - start) * 1000)

    return ParsedDocument(
        filename=Path(file_path).name,
        content_type="pdf",
        full_text=full_text,
        pages=pages,
        tables=tables,
        metadata={
            "page_count": len(doc.pages) if hasattr(doc, "pages") else 0,
        },
        page_count=len(doc.pages) if hasattr(doc, "pages") else 0,
        processing_time_ms=processing_time,
    )
```

### XLSX Parsing with openpyxl

```python
# Source: openpyxl official docs + reference project patterns
from openpyxl import load_workbook
from pathlib import Path
import time

async def parse_xlsx(file_path: str) -> "ParsedDocument":
    """Parse an XLSX file using openpyxl."""
    start = time.time()
    wb = load_workbook(file_path, data_only=True, read_only=True)

    all_text = []
    tables = []
    pages = []  # Each sheet = one "page"

    for sheet_idx, sheet_name in enumerate(wb.sheetnames):
        sheet = wb[sheet_name]
        sheet_text_parts = [f"=== Sheet: {sheet_name} ==="]
        sheet_data = []

        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                row_values = [str(cell) if cell is not None else "" for cell in row]
                sheet_data.append(row_values)
                sheet_text_parts.append(" | ".join(row_values))

        sheet_text = "\n".join(sheet_text_parts)
        all_text.append(sheet_text)

        pages.append(PageContent(
            page_number=sheet_idx + 1,
            text=sheet_text,
            tables=[{
                "sheet": sheet_name,
                "data": sheet_data,
                "rows": len(sheet_data),
                "cols": len(sheet_data[0]) if sheet_data else 0,
            }] if sheet_data else [],
        ))

        if sheet_data:
            tables.append({
                "page": sheet_idx + 1,
                "sheet": sheet_name,
                "headers": sheet_data[0] if sheet_data else [],
                "data": sheet_data[1:] if len(sheet_data) > 1 else sheet_data,
                "rows": len(sheet_data),
                "cols": len(sheet_data[0]) if sheet_data else 0,
            })

    wb.close()

    processing_time = int((time.time() - start) * 1000)

    return ParsedDocument(
        filename=Path(file_path).name,
        content_type="xlsx",
        full_text="\n\n".join(all_text),
        pages=pages,
        tables=tables,
        metadata={
            "sheet_count": len(wb.sheetnames),
            "sheet_names": wb.sheetnames,
        },
        page_count=len(wb.sheetnames),
        processing_time_ms=processing_time,
    )
```

### FastAPI Multi-File Upload Endpoint

```python
# Source: FastAPI official docs on file uploads
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import Annotated
import shutil
import uuid

@router.post("/projects/{project_id}/upload")
async def upload_documents(
    project_id: int,
    files: list[UploadFile] = File(..., description="Documents to upload"),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple documents to a project."""
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate and save files
    saved_files = []
    upload_dir = Path(settings.upload_dir) / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    allowed_extensions = {".pdf", ".docx", ".xlsx", ".xls"}

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in allowed_extensions:
            continue  # Skip unsupported files, don't fail entire upload

        # Generate unique filename to avoid collisions
        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        dest_path = upload_dir / safe_name

        # Stream to disk (don't load entire file into memory)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        saved_files.append({
            "original_name": file.filename,
            "saved_path": str(dest_path),
            "size": dest_path.stat().st_size,
            "extension": ext,
        })

    # Create document records
    for file_info in saved_files:
        doc = Document(
            project_id=project_id,
            filename=file_info["original_name"],
            file_path=file_info["saved_path"],
            file_type=file_info["extension"].lstrip("."),
            file_size=file_info["size"],
            status=DocumentStatus.PENDING,
        )
        db.add(doc)

    # Update project counts
    project.total_documents += len(saved_files)
    await db.commit()

    # Start background processing
    task_id = str(uuid.uuid4())
    asyncio.create_task(
        process_documents_batch(task_id, project_id, saved_files, db)
    )

    return {
        "task_id": task_id,
        "uploaded": len(saved_files),
        "skipped": len(files) - len(saved_files),
    }
```

### SSE Progress Streaming

```python
# Source: sse-starlette docs + FastAPI SSE patterns
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

# Simple in-memory progress store (sufficient for single-user v1)
_progress: dict[str, dict] = {}

async def process_documents_batch(
    task_id: str,
    project_id: int,
    files: list[dict],
    db_factory,
):
    """Process documents in background, updating progress store."""
    _progress[task_id] = {
        "status": "processing",
        "total": len(files),
        "processed": 0,
        "current_file": "",
        "errors": [],
    }

    for i, file_info in enumerate(files):
        _progress[task_id]["current_file"] = file_info["original_name"]
        try:
            # Parse based on file type
            parser = get_parser_for_extension(file_info["extension"])
            parsed = await parser.parse(file_info["saved_path"])
            # Update database record with parsed content
            # ... (update Document record with text, tables, metadata)
        except Exception as e:
            _progress[task_id]["errors"].append({
                "file": file_info["original_name"],
                "error": str(e),
            })

        _progress[task_id]["processed"] = i + 1

    _progress[task_id]["status"] = "completed"

@router.get("/progress/{task_id}")
async def stream_progress(task_id: str):
    """Stream processing progress via SSE."""
    async def generate():
        while True:
            data = _progress.get(task_id, {"status": "unknown"})
            yield {"data": json.dumps(data), "event": "progress"}
            if data.get("status") in ("completed", "failed", "unknown"):
                break
            await asyncio.sleep(0.5)
    return EventSourceResponse(generate())
```

### Alembic Async Setup

```python
# migrations/env.py (key parts for async SQLite)
# Source: Alembic cookbook + SQLAlchemy async docs
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import your models so Alembic can detect them
from app.database import Base
from app.models import project, document  # noqa: ensure models loaded

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```

### Minimal Jinja2 Upload UI

```html
<!-- app/templates/upload.html -->
<!-- Source: FastAPI templates docs + SSE browser API -->
<!DOCTYPE html>
<html>
<head>
    <title>BidOps AI - Upload Documents</title>
    <style>
        .progress-bar { width: 100%; background: #e0e0e0; border-radius: 4px; }
        .progress-fill { height: 24px; background: #4caf50; border-radius: 4px; transition: width 0.3s; }
        .file-item { padding: 8px; margin: 4px 0; background: #f5f5f5; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Upload Tender Documents</h1>
    <form id="uploadForm" enctype="multipart/form-data">
        <input type="file" name="files" multiple accept=".pdf,.docx,.xlsx,.xls" />
        <button type="submit">Upload & Process</button>
    </form>
    <div id="progress" style="display:none;">
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill" style="width:0%"></div>
        </div>
        <p id="progressText">Processing...</p>
    </div>
    <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const resp = await fetch('/api/projects/{{ project_id }}/upload', {
                method: 'POST', body: formData
            });
            const { task_id } = await resp.json();
            document.getElementById('progress').style.display = 'block';

            // Connect to SSE for progress
            const evtSource = new EventSource(`/api/progress/${task_id}`);
            evtSource.addEventListener('progress', (event) => {
                const data = JSON.parse(event.data);
                const pct = Math.round((data.processed / data.total) * 100);
                document.getElementById('progressFill').style.width = pct + '%';
                document.getElementById('progressText').textContent =
                    `Processing ${data.current_file} (${data.processed}/${data.total})`;
                if (data.status === 'completed') {
                    evtSource.close();
                    document.getElementById('progressText').textContent = 'All documents processed!';
                }
            });
        });
    </script>
</body>
</html>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyMuPDF + pdfplumber for PDF tables | Docling unified parser | 2024 (v1.0+) | Single library handles text, tables, OCR, layout for multiple formats |
| pytesseract for OCR | EasyOCR or Docling built-in OCR | 2023-2024 | Better accuracy, GPU support, simpler installation (no system binary needed for EasyOCR) |
| SQLAlchemy 1.4 Session pattern | SQLAlchemy 2.0 mapped_column + async | 2023 | Type-safe models, async natively, cleaner syntax |
| sync database access | async via aiosqlite | 2023+ | Non-blocking DB access, 3-5x better throughput under load |
| WebSocket for progress | SSE (Server-Sent Events) | Always (but gaining popularity) | Simpler for one-way progress, no connection upgrade needed |
| React SPA for every UI | Jinja2 + HTMX/vanilla JS | 2023-2025 trend | Simpler for CRUD/upload UIs, faster to build, no build step |
| Celery for background tasks | asyncio.create_task() for single-user | N/A | No broker dependency, sufficient for local single-user app |

**Deprecated/outdated:**
- `SQLAlchemy.Column()` syntax: Use `mapped_column()` with type annotations instead (SQLAlchemy 2.0+)
- `Docling export_to_dataframe()` without `doc=` parameter: Deprecated, always pass `doc=conv_res.document`
- `chromadb.Client(Settings(chroma_db_impl="duckdb+parquet"))`: Old ChromaDB API, use `chromadb.PersistentClient(path=...)` instead
- FastAPI `@app.on_event("startup")`: Deprecated in favor of `lifespan` context manager

## Open Questions

1. **Docling model caching on Windows**
   - What we know: Docling downloads models to HuggingFace cache directory (~/.cache/huggingface)
   - What's unclear: Whether Windows antivirus or corporate policies interfere with model downloads; exact disk space needed
   - Recommendation: Document first-run requirements; consider a pre-download script

2. **Docling DOCX table extraction quality**
   - What we know: Docling natively handles DOCX via InputFormat.DOCX with SimplePipeline backend
   - What's unclear: How well Docling extracts tables from DOCX versus python-docx's direct table access
   - Recommendation: Start with Docling for DOCX; fall back to python-docx if table quality is poor in testing

3. **SSE browser compatibility with EventSource**
   - What we know: EventSource API is supported in all modern browsers
   - What's unclear: Whether there are issues with long-running SSE connections on Windows localhost
   - Recommendation: Add a fallback polling endpoint (/progress/{task_id}/status) as insurance

4. **Docling processing speed for large PDFs**
   - What we know: Docling with ACCURATE table mode and OCR is slower than simpler parsers
   - What's unclear: Exact processing time for a typical 100+ page tender PDF on Windows
   - Recommendation: Add configurable timeout; provide "fast" vs "accurate" parsing options

5. **Alembic with async SQLite on Windows**
   - What we know: Alembic async template works with aiosqlite
   - What's unclear: Whether alembic autogenerate works reliably with aiosqlite on Windows (there is a known issue #898 about database file not found)
   - Recommendation: Use sync SQLAlchemy URL in alembic.ini (sqlite:///data/bidops.db) since migrations are CLI-only, not runtime

## Sources

### Primary (HIGH confidence)
- [Docling Official Documentation](https://docling-project.github.io/docling/) - DocumentConverter API, pipeline options, supported formats
- [Docling Pipeline Options Reference](https://docling-project.github.io/docling/reference/pipeline_options/) - PdfPipelineOptions, EasyOcrOptions, TableStructureOptions
- [Docling DoclingDocument Reference](https://docling-project.github.io/docling/reference/docling_document/) - iterate_items(), export_to_markdown(), tables access
- [FastAPI Official Docs - File Uploads](https://fastapi.tiangolo.com/tutorial/request-files/) - UploadFile, list[UploadFile], python-multipart
- [FastAPI Official Docs - Templates](https://fastapi.tiangolo.com/advanced/templates/) - Jinja2Templates setup
- [FastAPI Official Docs - Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) - BackgroundTasks usage
- [SQLAlchemy 2.0 Async Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - create_async_engine, async_sessionmaker
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) - Version compatibility, Windows support
- [Alembic Cookbook - Async](https://alembic.sqlalchemy.org/en/latest/cookbook.html) - Async migration setup

### Secondary (MEDIUM confidence)
- [Docling GitHub Issues #493](https://github.com/docling-project/docling/issues/493) - XLSX MIME type fix (resolved in docling-core v2.9.0)
- [Docling GitHub Issues #2269](https://github.com/docling-project/docling/issues/2269) - XLSX sheet selection limitation (unresolved)
- [Docling export_to_dataframe deprecation](https://github.com/docling-project/docling-core/issues/377) - Must pass doc= parameter
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette) - EventSourceResponse API
- [Medium: Setting up FastAPI with Async SQLAlchemy 2.0](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308)
- [Codecademy: Docling Complete Guide to Parsing](https://www.codecademy.com/article/docling-ai-a-complete-guide-to-parsing)

### Tertiary (LOW confidence)
- [Docling XLSX IndexError with picture description](https://github.com/docling-project/docling/issues/2390) - Active issue, avoid picture_description with XLSX
- [FastAPI + HTMX for server-rendered apps](https://medium.com/@strasbourgwebsolutions/fastapi-as-a-hypermedia-driven-application-w-htmx-jinja2templates-644c3bfa51d1) - Pattern for minimal UI approach

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs and PyPI, versions confirmed current
- Architecture: HIGH - Patterns derived from official FastAPI/SQLAlchemy docs and verified reference project
- Pitfalls: HIGH - Docling XLSX issues confirmed via GitHub issues; Windows/async pitfalls well-documented
- Code examples: MEDIUM - Based on official docs but some Docling iterate_items patterns not fully verified with latest API

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (30 days - stable libraries, Docling may release patches)
