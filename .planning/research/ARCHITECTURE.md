# Architecture Patterns: Document Intelligence System

**Domain:** Tender Document Intelligence / Construction Bidding Automation
**Researched:** 2026-02-04
**Confidence:** HIGH (multiple authoritative sources, aligned with project constraints)

## Executive Summary

A document intelligence system for tender automation follows a **pipeline-based RAG architecture** with five major subsystems: Document Ingestion, Vector Indexing, Retrieval & Generation, Structured Output, and Presentation. The architecture must handle multi-format documents (PDF, Word, Excel), bilingual content (Arabic/English), and produce citation-backed structured extractions.

For BidOps AI specifically, the recommended architecture is a **layered monolith** with clear service boundaries, optimized for local-first Windows deployment with FastAPI backend, ChromaDB vector store, and Gemini 3 Pro as the LLM.

---

## Recommended Architecture

```
+------------------------------------------------------------------+
|                        PRESENTATION LAYER                         |
|  [React SPA] <--REST API--> [FastAPI Backend]                    |
+------------------------------------------------------------------+
                                  |
+------------------------------------------------------------------+
|                         API LAYER (FastAPI)                       |
|  /projects  /documents  /extraction  /export                      |
+------------------------------------------------------------------+
                                  |
+------------------------------------------------------------------+
|                        SERVICE LAYER                              |
|  +----------------+  +------------------+  +------------------+   |
|  | DocumentService|  | ExtractionService|  | ExportService    |   |
|  +----------------+  +------------------+  +------------------+   |
|          |                    |                    |              |
|  +----------------+  +------------------+  +------------------+   |
|  | ParserRegistry |  | RetrievalService |  | TemplateEngine   |   |
|  +----------------+  +------------------+  +------------------+   |
+------------------------------------------------------------------+
                                  |
+------------------------------------------------------------------+
|                     INFRASTRUCTURE LAYER                          |
|  +----------+  +----------+  +----------+  +----------+          |
|  | SQLite   |  | ChromaDB |  | LangChain|  | File     |          |
|  | (metadata)|  | (vectors)|  | (LLM)   |  | System   |          |
|  +----------+  +----------+  +----------+  +----------+          |
+------------------------------------------------------------------+
```

---

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **ParserRegistry** | Route files to appropriate parser | File path + extension | Uniform ParsedDocument | DocumentService |
| **PDFParser** | Extract text/tables from PDFs | PDF file | ParsedDocument (text, pages, tables) | ParserRegistry |
| **DOCXParser** | Extract content from Word docs | DOCX file | ParsedDocument | ParserRegistry |
| **XLSXParser** | Extract sheets/tables from Excel | XLSX file | ParsedDocument (structured tables) | ParserRegistry |
| **ChunkingService** | Split documents into semantic chunks | ParsedDocument | List[Chunk] with metadata | DocumentService |
| **EmbeddingService** | Generate vector embeddings | Text chunks | Vector embeddings | IndexingService |
| **IndexingService** | Store/retrieve vectors | Chunks + embeddings | Indexed collection | ChromaDB |
| **RetrievalService** | Find relevant context for queries | Query + filters | Ranked chunks with scores | ChromaDB, EmbeddingService |
| **ExtractionService** | Orchestrate LLM-based extraction | Field definitions + context | Structured extractions with citations | RetrievalService, LLMService |
| **LLMService** | Interface with Gemini 3 Pro | Prompts | Completions | Google AI API |
| **CitationTracker** | Map extractions to source locations | LLM output + source chunks | Extraction with page/section refs | ExtractionService |
| **ExportService** | Generate output formats | Extraction results | JSON, Excel, PDF reports | TemplateEngine |
| **ProjectService** | Manage project metadata | CRUD operations | Project records | SQLite |
| **DocumentService** | Orchestrate document lifecycle | File uploads | Parsed, chunked, indexed docs | All parser/indexing services |

---

## Data Flow

### Flow 1: Document Ingestion Pipeline

```
[Tender Folder]
      |
      v
+-------------------+
| 1. File Discovery |  Scan folder, identify supported formats
+-------------------+
      |
      v
+-------------------+
| 2. Parser Routing |  PDFParser | DOCXParser | XLSXParser
+-------------------+
      |
      v
+-------------------+
| 3. Content        |  Extract text, tables, page numbers
|    Extraction     |  OCR for scanned PDFs (Arabic/English)
+-------------------+
      |
      v
+-------------------+
| 4. Chunking       |  Recursive text splitting (1000 chars, 200 overlap)
|                   |  Preserve page/section metadata per chunk
+-------------------+
      |
      v
+-------------------+
| 5. Embedding      |  sentence-transformers (multilingual model)
|                   |  paraphrase-multilingual-mpnet-base-v2
+-------------------+
      |
      v
+-------------------+
| 6. Indexing       |  Store in ChromaDB with metadata
|                   |  (doc_id, page, section, language)
+-------------------+
      |
      v
[SQLite: Document metadata, status, chunk counts]
```

**Critical Design Decisions:**

1. **Chunk metadata preservation**: Every chunk must retain `document_id`, `page_number`, `section_name` for citation tracking
2. **Bilingual embedding model**: Use multilingual model that handles Arabic and English in same vector space
3. **Table handling**: Extract tables as structured data AND as text descriptions for different query types

### Flow 2: Extraction with Citations

```
[User triggers extraction]
      |
      v
+------------------------+
| 1. Field Definition    |  Load extraction schema (project_name, owner,
|    Loading             |  dates, scope, requirements, etc.)
+------------------------+
      |
      v
+------------------------+
| 2. Per-Field Retrieval |  For each field:
|                        |  - Generate query from field description
|                        |  - Retrieve top-k relevant chunks
|                        |  - Filter by confidence threshold
+------------------------+
      |
      v
+------------------------+
| 3. Context Assembly    |  Combine chunks with source metadata
|                        |  Format: "[DOC:filename PAGE:X] content..."
+------------------------+
      |
      v
+------------------------+
| 4. LLM Extraction      |  Prompt with:
|                        |  - Field definition + expected format
|                        |  - Retrieved context with citations
|                        |  - Instruction to cite sources
+------------------------+
      |
      v
+------------------------+
| 5. Output Parsing      |  Parse structured output (Pydantic model)
|                        |  Extract value + confidence + citations
+------------------------+
      |
      v
+------------------------+
| 6. Citation Resolution |  Map citation markers to source docs
|                        |  Verify cited pages contain claimed info
+------------------------+
      |
      v
[Extraction Result: {value, confidence, citations: [{doc, page, quote}]}]
```

**Citation Strategy (Anthropic-style):**

```python
# Prompt template for extraction with citations
"""
Extract {field_name} from the following documents.

CONTEXT:
{for chunk in chunks}
[SOURCE:{chunk.doc_id}|PAGE:{chunk.page}] {chunk.text}
{endfor}

INSTRUCTIONS:
1. Extract the {field_name} value
2. For EVERY claim, include a citation in format [SOURCE:X|PAGE:Y]
3. If information is ambiguous or conflicting, note all sources
4. If not found, respond with "NOT_FOUND" and explain what you searched

OUTPUT FORMAT:
{
  "value": "extracted value",
  "confidence": 0.0-1.0,
  "citations": [
    {"source": "doc_id", "page": N, "quote": "relevant excerpt"}
  ],
  "notes": "any caveats or conflicts"
}
"""
```

### Flow 3: Structured Output Generation

```
[Extraction Results]
      |
      v
+------------------------+
| 1. Schema Validation   |  Validate against Pydantic models
|                        |  Flag missing required fields
+------------------------+
      |
      v
+------------------------+
| 2. Format Selection    |  JSON | Excel | PDF Report
+------------------------+
      |
   +--+--+
   |     |
   v     v
+------+ +--------+
| JSON | | Excel  |  Use openpyxl with templates
+------+ +--------+  Populate cells, apply formatting
   |     |
   +--+--+
      |
      v
+------------------------+
| 3. Citation Appendix   |  Generate source reference section
|                        |  Link each extraction to evidence
+------------------------+
      |
      v
[Output Files: summary.json, requirements.xlsx, report.pdf]
```

---

## Patterns to Follow

### Pattern 1: Parser Registry (Strategy Pattern)

**What:** Central registry that routes files to appropriate parsers based on extension/MIME type.

**Why:** Decouples file type detection from parsing logic. Easy to add new formats.

**Implementation:**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path

@dataclass
class ParsedDocument:
    """Uniform output from all parsers"""
    document_id: str
    filename: str
    content: str  # Full text content
    pages: List[PageContent]  # Per-page breakdown
    tables: List[TableContent]  # Extracted tables
    metadata: Dict  # Format-specific metadata
    language: Optional[str]  # Detected language

@dataclass
class PageContent:
    page_number: int
    text: str
    tables: List[TableContent]

@dataclass
class TableContent:
    page_number: int
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str]

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        pass

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        pass

class ParserRegistry:
    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}

    def register(self, parser: BaseParser):
        for ext in parser.supported_extensions():
            self._parsers[ext.lower()] = parser

    def parse(self, file_path: Path) -> ParsedDocument:
        ext = file_path.suffix.lower()
        if ext not in self._parsers:
            raise ValueError(f"No parser registered for {ext}")
        return self._parsers[ext].parse(file_path)
```

### Pattern 2: Chunking with Metadata Preservation

**What:** Split documents while preserving source location for citations.

**Why:** Citations require knowing exactly where each chunk came from.

**Implementation:**

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

@dataclass
class Chunk:
    text: str
    document_id: str
    page_number: int
    section_name: Optional[str]
    char_start: int
    char_end: int

class ChunkingService:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def chunk_document(self, doc: ParsedDocument) -> List[Chunk]:
        chunks = []
        for page in doc.pages:
            page_chunks = self.splitter.split_text(page.text)
            char_offset = 0
            for chunk_text in page_chunks:
                chunks.append(Chunk(
                    text=chunk_text,
                    document_id=doc.document_id,
                    page_number=page.page_number,
                    section_name=self._detect_section(chunk_text),
                    char_start=char_offset,
                    char_end=char_offset + len(chunk_text)
                ))
                char_offset += len(chunk_text) - self.splitter._chunk_overlap
        return chunks
```

### Pattern 3: Hybrid Retrieval (Dense + Sparse)

**What:** Combine semantic (vector) search with keyword (BM25) search.

**Why:** Semantic search captures meaning but misses exact terms. Keywords catch specific terminology (tender numbers, company names). Construction documents have many domain-specific terms.

**Implementation:**

```python
from chromadb import Collection
from rank_bm25 import BM25Okapi

class HybridRetriever:
    def __init__(self, collection: Collection, alpha: float = 0.7):
        """alpha: weight for semantic search (1-alpha for keyword)"""
        self.collection = collection
        self.alpha = alpha
        self._build_bm25_index()

    def _build_bm25_index(self):
        # Build BM25 index from all chunks
        results = self.collection.get(include=["documents"])
        self.corpus = results["documents"]
        tokenized = [doc.lower().split() for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        self.doc_ids = results["ids"]

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        # Semantic search
        semantic_results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 2
        )

        # Keyword search
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # Combine scores with RRF (Reciprocal Rank Fusion)
        combined = self._reciprocal_rank_fusion(
            semantic_results, bm25_scores, top_k
        )
        return combined
```

### Pattern 4: Extraction Schema Definition

**What:** Define extraction fields with prompts, types, and validation rules.

**Why:** Consistent extraction across all projects. Easy to extend field set.

**Implementation:**

```python
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum

class FieldType(str, Enum):
    TEXT = "text"
    DATE = "date"
    CURRENCY = "currency"
    LIST = "list"
    BOOLEAN = "boolean"

@dataclass
class ExtractionField:
    name: str
    description: str
    field_type: FieldType
    query_hints: List[str]  # Keywords to boost retrieval
    required: bool = True
    validation_regex: Optional[str] = None
    examples: List[str] = None

# Project Summary Schema
PROJECT_SUMMARY_FIELDS = [
    ExtractionField(
        name="project_name",
        description="Official name of the construction project",
        field_type=FieldType.TEXT,
        query_hints=["project name", "project title", "tender for"],
        examples=["New Cairo Hospital Phase 2", "Alexandria Port Expansion"]
    ),
    ExtractionField(
        name="project_owner",
        description="Client or owner organization commissioning the project",
        field_type=FieldType.TEXT,
        query_hints=["owner", "client", "employer", "authority"]
    ),
    ExtractionField(
        name="submission_deadline",
        description="Final date and time for tender submission",
        field_type=FieldType.DATE,
        query_hints=["deadline", "submission date", "due date", "closing date"]
    ),
    # ... more fields
]
```

### Pattern 5: Service Layer with Dependency Injection

**What:** Services receive dependencies via constructor, not global state.

**Why:** Testable, configurable, clear boundaries.

**Implementation:**

```python
class ExtractionService:
    def __init__(
        self,
        retriever: RetrievalService,
        llm: LLMService,
        schema: List[ExtractionField]
    ):
        self.retriever = retriever
        self.llm = llm
        self.schema = schema

    async def extract_project_summary(
        self,
        project_id: str
    ) -> ProjectSummary:
        results = {}
        for field in self.schema:
            # Retrieve relevant context
            chunks = await self.retriever.retrieve(
                query=field.description,
                hints=field.query_hints,
                project_id=project_id
            )

            # Extract with LLM
            extraction = await self.llm.extract_field(
                field=field,
                context=chunks
            )

            results[field.name] = extraction

        return ProjectSummary(**results)

# FastAPI dependency injection
def get_extraction_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
) -> ExtractionService:
    retriever = RetrievalService(
        collection=get_chroma_collection(settings.chroma_path)
    )
    llm = LLMService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model
    )
    return ExtractionService(retriever, llm, PROJECT_SUMMARY_FIELDS)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic Document Processing

**What:** Processing entire documents in one pass without chunking.

**Why bad:**
- Exceeds LLM context windows (even large ones)
- Poor retrieval precision (needle in haystack)
- No citation granularity

**Instead:** Chunk early, chunk with metadata, retrieve selectively.

### Anti-Pattern 2: Embedding at Query Time

**What:** Re-embedding document content for every query.

**Why bad:**
- Massive latency (minutes for large doc sets)
- Wasted compute (same content embedded repeatedly)
- Poor user experience

**Instead:** Embed once during ingestion, store in vector DB, query by similarity.

### Anti-Pattern 3: Trust LLM Output Without Validation

**What:** Accepting LLM extractions as-is without schema validation or citation verification.

**Why bad:**
- Hallucinated values slip through
- Format inconsistencies break downstream processing
- Citations may reference non-existent pages

**Instead:**
- Pydantic models for output parsing
- Citation verification (does cited page contain the value?)
- Confidence thresholds for human review flags

### Anti-Pattern 4: Single Retrieval Strategy

**What:** Using only semantic search for all queries.

**Why bad:**
- Misses exact matches (tender numbers, company names, dates)
- Domain terminology may not embed well
- Arabic proper nouns often missed

**Instead:** Hybrid retrieval (semantic + keyword). Weight based on query type.

### Anti-Pattern 5: Synchronous Document Processing

**What:** Processing documents in the API request thread.

**Why bad:**
- Request timeouts for large documents
- Poor UX (user waits minutes)
- Blocks other requests

**Instead:**
- Return immediately with job ID
- Process in background (async task or worker)
- Poll for status or use WebSocket for progress

### Anti-Pattern 6: Storing Embeddings in SQLite

**What:** Using SQLite to store and query vector embeddings.

**Why bad:**
- No native vector similarity search
- Terrible query performance at scale
- Missing metadata filtering

**Instead:** Use purpose-built vector DB (ChromaDB for local, Qdrant/Pinecone for scale).

---

## Bilingual (Arabic/English) Considerations

### Embedding Model Selection

**Recommended:** `paraphrase-multilingual-mpnet-base-v2` from sentence-transformers

**Why:**
- Trained on 50+ languages including Arabic
- Same vector space for Arabic and English (cross-lingual retrieval)
- Good quality, reasonable size (420MB)

**Alternative:** `intfloat/multilingual-e5-large` for higher quality at larger size

### OCR for Arabic Documents

**Challenge:** Many Arabic PDFs are scanned images, not text.

**Solution Stack:**
1. **Detection:** Check if PDF has extractable text vs. images
2. **OCR Engine:** Tesseract with Arabic language pack (`ara`)
3. **Preprocessing:** Deskew, denoise, binarize for better OCR
4. **Post-processing:** Arabic text normalization (tashkeel removal optional)

```python
import pytesseract
from pdf2image import convert_from_path

def ocr_arabic_pdf(pdf_path: Path) -> List[PageContent]:
    pages = convert_from_path(pdf_path, dpi=300)
    results = []
    for i, page_image in enumerate(pages):
        # OCR with Arabic + English
        text = pytesseract.image_to_string(
            page_image,
            lang='ara+eng',
            config='--psm 1'  # Automatic page segmentation with OSD
        )
        results.append(PageContent(page_number=i+1, text=text, tables=[]))
    return results
```

### Language Detection and Routing

```python
from langdetect import detect

def detect_document_language(text: str) -> str:
    """Detect primary language, handle mixed content."""
    try:
        lang = detect(text[:5000])  # Sample first 5000 chars
        return 'ar' if lang == 'ar' else 'en'
    except:
        return 'unknown'
```

---

## Local-First Windows Deployment Architecture

### Component Deployment

```
[Windows Machine]
|
+-- BidOps AI/
    |
    +-- backend/
    |   +-- main.py          # FastAPI app
    |   +-- uvicorn.exe      # ASGI server (bundled or installed)
    |
    +-- frontend/
    |   +-- dist/            # Built React app (static files)
    |
    +-- data/
    |   +-- bidops.db        # SQLite database
    |   +-- chroma/          # ChromaDB persistent storage
    |   +-- uploads/         # Uploaded document files
    |   +-- exports/         # Generated output files
    |
    +-- config/
    |   +-- .env             # Environment variables
    |
    +-- logs/
        +-- app.log          # Application logs
```

### Startup Sequence

```python
# main.py - Application entry point
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import chromadb

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_database()  # SQLite migrations
    init_chromadb()  # ChromaDB collection creation
    verify_tesseract()  # Check OCR availability
    yield
    # Shutdown
    cleanup_temp_files()

app = FastAPI(lifespan=lifespan)

# Serve React frontend from /
app.mount("/", StaticFiles(directory="frontend/dist", html=True))

# API routes under /api
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

### ChromaDB Local Configuration

```python
import chromadb
from chromadb.config import Settings

def get_chroma_client(persist_directory: str) -> chromadb.Client:
    """Initialize ChromaDB with local persistence."""
    return chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory=persist_directory,
        anonymized_telemetry=False
    ))

def get_or_create_collection(
    client: chromadb.Client,
    project_id: str
) -> chromadb.Collection:
    """One collection per project for isolation."""
    return client.get_or_create_collection(
        name=f"project_{project_id}",
        metadata={"hnsw:space": "cosine"}
    )
```

### Windows-Specific Considerations

1. **Path Handling:** Use `pathlib.Path` consistently, handle backslashes
2. **File Locking:** SQLite and ChromaDB handle this, but be careful with concurrent writes
3. **Tesseract Installation:** Requires separate install, set `TESSDATA_PREFIX` env var
4. **Process Management:** Use `pythonw.exe` for background service (no console window)
5. **Firewall:** Bind to `127.0.0.1` only for security (no external access)

---

## Suggested Build Order

Based on component dependencies, build in this order:

### Phase 1: Foundation (Must build first)

| Component | Why First | Dependencies | Deliverable |
|-----------|-----------|--------------|-------------|
| **Project/SQLite Setup** | Everything needs data storage | None | DB schema, CRUD operations |
| **ParserRegistry + PDFParser** | Documents are the input | None | Parse PDF -> ParsedDocument |
| **ChunkingService** | Required for indexing | ParserRegistry | Chunks with metadata |

**Phase 1 validates:** "Can we ingest and chunk a PDF?"

### Phase 2: Indexing & Retrieval (Core RAG)

| Component | Why Next | Dependencies | Deliverable |
|-----------|----------|--------------|-------------|
| **EmbeddingService** | Vectors for ChromaDB | Chunking | Chunk -> vector |
| **ChromaDB Integration** | Store and search vectors | Embedding | Index/query operations |
| **RetrievalService** | Get relevant context | ChromaDB, Embedding | Query -> ranked chunks |

**Phase 2 validates:** "Can we find relevant chunks for a query?"

### Phase 3: LLM Extraction

| Component | Why Next | Dependencies | Deliverable |
|-----------|----------|--------------|-------------|
| **LLMService (Gemini)** | Core extraction engine | None (API) | Prompt -> completion |
| **ExtractionService** | Orchestrate extraction | Retrieval, LLM | Field -> extraction |
| **CitationTracker** | Evidence linking | Extraction | Extraction with sources |

**Phase 3 validates:** "Can we extract a field with citation?"

### Phase 4: Additional Parsers

| Component | Why Now | Dependencies | Deliverable |
|-----------|---------|--------------|-------------|
| **DOCXParser** | Word docs common in tenders | ParserRegistry | Parse DOCX |
| **XLSXParser** | BOQs are Excel | ParserRegistry | Parse Excel -> tables |
| **OCR Integration** | Scanned PDFs | PDFParser | Text from images |

**Phase 4 validates:** "Can we handle all v1 document types?"

### Phase 5: Output Generation

| Component | Why Now | Dependencies | Deliverable |
|-----------|---------|--------------|-------------|
| **ExportService** | Users need outputs | Extraction | JSON/Excel/PDF |
| **TemplateEngine** | Formatted reports | None | Render templates |
| **RequirementsChecklist** | Core feature | Extraction | Checklist generation |

**Phase 5 validates:** "Can we produce the deliverables users need?"

### Phase 6: API & UI

| Component | Why Last | Dependencies | Deliverable |
|-----------|----------|--------------|-------------|
| **FastAPI Routes** | Expose everything | All services | REST API |
| **React Frontend** | User interface | API | Web UI |
| **Background Jobs** | Large doc processing | Services | Async processing |

**Phase 6 validates:** "Can users accomplish their workflow?"

---

## Scalability Considerations

| Concern | Local (1 user) | Small Team (5 users) | Enterprise |
|---------|----------------|---------------------|------------|
| **Vector Storage** | ChromaDB local | ChromaDB persistent | Qdrant/Pinecone cloud |
| **Database** | SQLite | PostgreSQL | PostgreSQL + read replicas |
| **Document Processing** | Sync in-process | Background workers | Celery/Redis queue |
| **LLM Calls** | Sequential | Rate-limited concurrent | Batch API, caching |
| **File Storage** | Local filesystem | NAS/shared drive | S3/Azure Blob |

For BidOps AI v1 (local, single user), the leftmost column is appropriate.

---

## Sources

**RAG Architecture (HIGH confidence):**
- [Building Production RAG Systems in 2026](https://brlikhon.engineer/blog/building-production-rag-systems-in-2026-complete-architecture-guide)
- [LangChain RAG Documentation](https://docs.langchain.com/oss/python/langchain/rag)
- [How to Build Production-Ready RAG Applications with LangChain and FastAPI](https://www.bitcot.com/build-rag-applications-with-langchain-and-fastapi/)

**Document Parsing (HIGH confidence):**
- [Docling - IBM Document Parser](https://github.com/docling-project/docling)
- [PyMuPDF4LLM Guide](https://medium.com/@danushidk507/using-pymupdf4llm-a-practical-guide-for-pdf-extraction-in-llm-rag-environments-63649915abbf)
- [PDF Parsing Tools Comparison](https://arxiv.org/html/2410.09871v1)

**Citation & Attribution (MEDIUM confidence):**
- [RAG with Citations - Zilliz](https://zilliz.com/blog/retrieval-augmented-generation-with-citations)
- [Anthropic-Style Citations](https://medium.com/data-science-collective/anthropic-style-citations-with-any-llm-2c061671ddd5)

**ChromaDB (HIGH confidence):**
- [ChromaDB Official](https://www.trychroma.com/)
- [ChromaDB GitHub](https://github.com/chroma-core/chroma)

**Arabic NLP (MEDIUM confidence):**
- [Arabic NLP Comprehensive Review](https://www.mdpi.com/2073-431X/14/11/497)
- [NYU Arabic NLP Research](https://nyuad.nyu.edu/en/research/faculty-labs-and-projects/computational-approaches-to-modeling-language-lab/research/arabic-natural-language-processing.html)

**FastAPI Best Practices (HIGH confidence):**
- [FastAPI Best Practices GitHub](https://github.com/zhanymkanov/fastapi-best-practices)
- [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture)

**Local LLM Deployment (MEDIUM confidence):**
- [Microsoft Foundry Local](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/transform-your-ai-applications-with-local-llm-deployment/4462829)
- [Best LLM Tools for Local Deployment 2026](https://www.unite.ai/best-llm-tools-to-run-models-locally/)

---

*Architecture research: 2026-02-04*
