# Technology Stack: BidOps AI

**Project:** Tender Document Intelligence System for Construction Bidding
**Researched:** 2026-02-04
**Focus:** Document ingestion, bilingual (Arabic/English) processing, structured extraction with citations

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| FastAPI | 0.128.0 | REST API backend | Async-first design, native file upload handling with `UploadFile`, automatic OpenAPI docs, Pydantic integration for structured responses. Best-in-class for document processing APIs. | HIGH |
| Uvicorn | latest | ASGI server | FastAPI's recommended production server, included in `fastapi[standard]` | HIGH |
| Python | 3.10+ | Runtime | Required by Docling (>=3.10), google-genai (>=3.10), LangChain (>=3.10). Use 3.11 or 3.12 for best performance. | HIGH |

### Document Ingestion Layer

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Docling** | 2.72.0 | Primary document parser | IBM's unified parser handles PDF, DOCX, XLSX, PPTX. 97.9% accuracy on complex tables. Outputs to Markdown/JSON. Native LangChain integration. Handles multi-format tenders in one library. | HIGH |
| PyMuPDF4LLM | latest | PDF fallback / Markdown extraction | Optimized for RAG workflows. Fast (0.12s benchmark). Use when Docling struggles with specific PDFs. Dual-license (AGPL/commercial). | HIGH |
| python-docx | 1.2.0 | Word doc metadata | Docling handles content extraction; use python-docx for programmatic .docx metadata access when needed. | HIGH |
| openpyxl | 3.1.5 | Excel metadata | Docling handles sheet content; use openpyxl for direct cell/formula access and metadata extraction. | HIGH |

### OCR for Scanned Documents

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **EasyOCR** | 1.7.2 | Bilingual OCR (Arabic + English) | Supports 80+ languages including Arabic. Handles RTL text and mixed scripts on same page. PyTorch-based, works offline. Better Arabic accuracy than Tesseract. | HIGH |
| Docling OCR | integrated | OCR within Docling | Docling has extensive built-in OCR support. Try Docling's OCR first; fall back to EasyOCR for difficult Arabic scans. | MEDIUM |

**Arabic OCR Note:** Arabic presents unique challenges - characters change form based on position, RTL layout, mixed numeral systems. EasyOCR handles these well but verify output on your specific document types. Consider Google Document AI for production-critical Arabic if EasyOCR accuracy is insufficient.

### LLM Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **google-genai** | 1.61.0 | Gemini API SDK | Official Google SDK. Supports Gemini 3 Pro. Native document understanding (up to 1000 PDF pages). Structured outputs with JSON schema/Pydantic. Dual API support (Gemini Developer API + Vertex AI). | HIGH |
| LangChain | 1.2.8 | Orchestration framework | RAG pipeline construction, document loaders, text splitters, chain composition. Direct Docling integration. Agent capabilities for complex extraction. | HIGH |

**Gemini 3 Pro Capabilities (verified):**
- Native PDF understanding - analyzes text, images, tables, charts, diagrams
- Up to 1000 pages per document, 50MB max file size
- Structured output with JSON schema - Pydantic models work directly
- Embedded text in PDFs is extracted without token charges
- Supports combining with tools (Grounding, URL Context, Function Calling)

### Vector Database & Embeddings

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **ChromaDB** | 1.4.1 | Vector store | Local-first, zero-config, pip install ready. Perfect for Windows desktop app. 4x faster since Rust-core rewrite. SQLite-like simplicity. Includes metadata filtering. | HIGH |
| sentence-transformers | 5.2.2 | Embedding models | Access to multilingual models on HuggingFace. Local inference, no API costs. | HIGH |
| **paraphrase-multilingual-mpnet-base-v2** | - | Embedding model | 768-dim vectors. Supports Arabic + English in shared space. Strong cross-lingual retrieval. Well-tested for bilingual document search. | HIGH |

**Alternative Embedding Models for Arabic:**
- `gte-multilingual-base` (Alibaba): 305M params, 70+ languages, strong retrieval performance
- `BGE-M3`: 100+ languages, 8192 token context, hybrid retrieval support
- Arabic-specific Matryoshka models: 83.16 on STS17 benchmark, but less tested

**ChromaDB vs Qdrant Decision:**
Use ChromaDB because:
1. Zero-config local mode - critical for Windows desktop deployment
2. No separate server process required
3. Built-in metadata + full-text search
4. Sufficient for tender document corpus (< 1M vectors)

Consider Qdrant (`qdrant-client` 1.16.2) only if you need:
- Massive scale (50M+ vectors)
- Advanced filtering during HNSW traversal
- Distributed deployment

### Structured Extraction with Citations

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Pydantic** | 2.x | Schema definition | Define extraction schemas as Python classes. Gemini + LangChain both support Pydantic natively. Type safety + validation built-in. | HIGH |
| **instructor** | latest | Structured LLM output | Works with google-genai SDK. Provides `GENAI_TOOLS` and `GENAI_STRUCTURED_OUTPUTS` modes. Handles retries and validation. | HIGH |

**Citation Strategy:**
Gemini 3 + Docling enables page-level citations:
1. Docling extracts with `page_chunks=True` - each chunk includes page metadata
2. Store page numbers in ChromaDB metadata
3. Gemini retrieves relevant chunks with page references
4. Structure output to include `source_pages: list[int]` field

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | latest | File uploads | Required by FastAPI for `UploadFile` |
| python-magic | latest | File type validation | Validate uploads by magic numbers, not just extension |
| aiofiles | latest | Async file I/O | Async file writes during upload processing |
| pydantic-settings | 2.x | Configuration | Environment-based config management |
| httpx | latest | HTTP client | Async HTTP for external APIs |
| tqdm | latest | Progress bars | Document processing progress feedback |

---

## What NOT to Use (and Why)

| Technology | Why Avoid | Use Instead |
|------------|-----------|-------------|
| **Tesseract** (pytesseract) | Poor Arabic accuracy compared to EasyOCR. Requires separate binary installation. | EasyOCR |
| **pdfplumber** | Good for tables but slower than PyMuPDF. Doesn't match Docling's unified approach. | Docling |
| **Unstructured.io** | Heavier dependency, cloud-oriented. Docling is faster and more accurate for tables (97.9% vs lower). | Docling |
| **LlamaIndex** | Good framework but LangChain has better Docling integration and more FastAPI examples. | LangChain |
| **Pinecone/Weaviate** | Cloud-hosted vector DBs. Project requires local Windows operation. | ChromaDB |
| **OpenAI API** | Project specifies Gemini 3 Pro. Gemini has better native document understanding. | google-genai |
| **SQLAlchemy** | Overkill for this project - ChromaDB handles embeddings, Pydantic handles data models. | ChromaDB + JSON files |
| **Celery** | Heavy task queue. Use FastAPI's BackgroundTasks for document processing. | BackgroundTasks |

---

## Arabic/Bilingual Handling Specifics

### Critical Considerations

1. **Embedding Model Selection**
   - Use `paraphrase-multilingual-mpnet-base-v2` - proven Arabic support
   - Test on your actual tender documents before committing
   - Arabic text may need normalization (remove tashkeel/diacritics) for consistent embeddings

2. **Text Normalization**
   ```python
   import re

   def normalize_arabic(text: str) -> str:
       """Normalize Arabic text for consistent processing."""
       # Remove tashkeel (diacritics)
       text = re.sub(r'[\u064B-\u0652]', '', text)
       # Normalize alef variants to bare alef
       text = re.sub(r'[\u0622\u0623\u0625]', '\u0627', text)
       # Normalize teh marbuta to heh
       text = text.replace('\u0629', '\u0647')
       return text
   ```

3. **RTL Layout in PDFs**
   - Docling handles reading order detection
   - Verify table column order in extracted data
   - Test with sample bilingual tenders before production

4. **Mixed Language Documents**
   - Common in construction tenders: Arabic body + English specs
   - EasyOCR handles mixed scripts on same page
   - Embedding model handles cross-lingual semantic search

5. **Font Considerations**
   - Some Arabic fonts in PDFs may not extract cleanly
   - OCR fallback (EasyOCR) needed for image-based Arabic text

---

## Installation

```bash
# Create virtual environment (Python 3.11 recommended)
python -m venv venv
venv\Scripts\activate  # Windows

# Core framework
pip install "fastapi[standard]"

# Document processing
pip install docling pymupdf4llm python-docx openpyxl

# OCR (Arabic support)
pip install easyocr

# LLM & RAG
pip install google-genai langchain langchain-google-genai

# Vector database & embeddings
pip install chromadb sentence-transformers

# Structured extraction
pip install instructor pydantic-settings

# File handling
pip install python-multipart python-magic-bin aiofiles

# Note: python-magic-bin is the Windows-compatible version
```

### GPU Support (Optional but Recommended)

```bash
# For faster EasyOCR and sentence-transformers
# Install PyTorch with CUDA first (check pytorch.org for your CUDA version)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## Architecture Implications

### Document Processing Pipeline

```
Tender Folder (PDF, DOCX, XLSX)
         |
         v
    [Docling Parser]
         |
    (text, tables, metadata, page numbers)
         |
         v
    [Embeddings] --> [ChromaDB]
         |
         v
    [Gemini 3 Pro + RAG]
         |
    (structured extraction with citations)
         |
         v
    [Pydantic Models]
         |
         v
    [FastAPI Response]
```

### Key Integration Points

1. **Docling -> LangChain**: Use `DoclingLoader` for seamless integration
2. **LangChain -> ChromaDB**: Built-in `Chroma` vectorstore
3. **LangChain -> Gemini**: Use `langchain-google-genai` package
4. **Gemini -> Pydantic**: Native structured output with JSON schema

---

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| FastAPI | HIGH | Verified version, mature ecosystem, clear best practice for Python APIs |
| Docling | HIGH | Verified v2.72.0, IBM-backed, 97.9% table accuracy benchmarked |
| google-genai | HIGH | Verified v1.61.0, official SDK, document understanding confirmed |
| ChromaDB | HIGH | Verified v1.4.1, local-first matches requirements |
| EasyOCR | HIGH | Verified v1.7.2, Arabic support confirmed, widely used |
| paraphrase-multilingual-mpnet-base-v2 | MEDIUM | Well-documented but test on actual Arabic tender content recommended |
| Instructor library | MEDIUM | Works with google-genai but verify specific Gemini 3 compatibility |

---

## Sources

### Official Documentation (HIGH confidence)
- [PyMuPDF on PyPI](https://pypi.org/project/PyMuPDF/) - v1.26.7 verified
- [ChromaDB on PyPI](https://pypi.org/project/chromadb/) - v1.4.1 verified
- [Docling on PyPI](https://pypi.org/project/docling/) - v2.72.0 verified
- [google-genai on PyPI](https://pypi.org/project/google-genai/) - v1.61.0 verified
- [FastAPI on PyPI](https://pypi.org/project/fastapi/) - v0.128.0 verified
- [LangChain on PyPI](https://pypi.org/project/langchain/) - v1.2.8 verified
- [sentence-transformers on PyPI](https://pypi.org/project/sentence-transformers/) - v5.2.2 verified
- [EasyOCR on PyPI](https://pypi.org/project/easyocr/) - v1.7.2 verified
- [qdrant-client on PyPI](https://pypi.org/project/qdrant-client/) - v1.16.2 verified
- [Gemini API Document Processing](https://ai.google.dev/gemini-api/docs/document-processing) - capabilities confirmed

### Benchmarks & Comparisons (MEDIUM confidence)
- [PDF Table Extraction Benchmark](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/) - Docling 97.9% accuracy
- [Vector Database Comparison 2025](https://liquidmetal.ai/casesAndBlogs/vector-comparison/) - ChromaDB vs Qdrant analysis
- [Best Open-Source Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Multilingual Sentence Transformers](https://www.sbert.net/examples/training/multilingual/README.html)

### Arabic-Specific Resources (MEDIUM confidence)
- [EasyOCR Multilingual OCR](https://www.aitoolnet.com/easyocr) - Arabic support confirmed
- [Arabic Matryoshka Embedding Models](https://huggingface.co/collections/Omartificial-Intelligence-Space/arabic-matryoshka-and-gate-embedding-models)
- [Sentence Transformers Arabic Comparison](https://github.com/m-elbeltagi/Comparing_Arabic_Sentence_Transformers)

---

## Open Questions for Phase-Specific Research

1. **Arabic Embedding Quality**: Test `paraphrase-multilingual-mpnet-base-v2` on actual tender documents. May need Arabic-specific fine-tuning.

2. **Gemini 3 Pro Availability**: Verify Gemini 3 Pro API access in your region. Fallback to Gemini 2.0 if needed.

3. **Docling OCR vs EasyOCR**: Test both on scanned Arabic tenders to determine optimal pipeline.

4. **Citation Granularity**: Determine if page-level citations suffice or if paragraph/sentence-level needed.

5. **Windows File Locking**: Test concurrent document processing - Windows handles file locks differently than Linux.
