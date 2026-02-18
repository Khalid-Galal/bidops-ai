# Phase 2: Bilingual Processing & Search - Research

**Researched:** 2026-02-19
**Domain:** Arabic OCR, bilingual text processing, vector indexing, semantic chunking, hybrid search
**Confidence:** HIGH

## Summary

Phase 2 extends the Phase 1 ingestion pipeline with three capabilities: (1) Arabic OCR and bilingual text processing so that scanned Arabic documents produce clean, correctly-ordered text; (2) vector indexing via ChromaDB with multilingual embeddings so all document content is semantically searchable; and (3) hybrid search combining keyword (BM25) and vector similarity so users can find content by exact term or by meaning across languages.

The primary technical challenges are: Arabic RTL/LTR bidirectional text corruption when numbers appear inside Arabic sentences, the 128-token max sequence length of the recommended embedding model (requiring careful chunk sizing), and implementing hybrid search locally since ChromaDB's new BM25/Search API is cloud-only. The approach is: add `"ar"` to EasyOCR's lang list in the existing Docling pipeline, add post-OCR Arabic text normalization, use `lingua-language-detector` for per-section language detection, chunk documents at semantic boundaries preserving page/section metadata, embed with `paraphrase-multilingual-mpnet-base-v2` via ChromaDB's built-in `SentenceTransformerEmbeddingFunction`, build a parallel BM25 index with `rank-bm25`, and fuse results with Reciprocal Rank Fusion (RRF).

**Primary recommendation:** Extend the existing PdfParser to add Arabic (`"ar"`) to EasyOCR's lang list, implement a post-processing pipeline for Arabic text normalization and language detection, chunk at semantic boundaries (respecting paragraphs, tables, sections) into ~400-500 character chunks (to stay within the 128-token limit after tokenization), index into ChromaDB with `SentenceTransformerEmbeddingFunction` using `paraphrase-multilingual-mpnet-base-v2`, and implement hybrid search by combining ChromaDB vector queries with a parallel `rank-bm25` BM25 index fused via RRF.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LANG-01 | System handles Arabic text correctly with RTL support | EasyOCR Arabic lang support + PyArabic normalization + `python-bidi` for logical-to-visual ordering. Docling already handles reading order detection. Post-OCR validation for number ordering. |
| LANG-03 | System handles mixed Arabic/English documents on the same page | EasyOCR natively handles mixed Arabic+English scripts on same page. `lingua-language-detector` `detect_multiple_languages_of()` identifies per-section language boundaries. Multilingual embedding model places both languages in shared vector space. |
| LANG-04 | System performs Arabic OCR on scanned Arabic documents | Change `EasyOcrOptions(lang=["en"])` to `EasyOcrOptions(lang=["en", "ar"])` in existing PdfParser's Docling pipeline. EasyOCR 1.7.2 supports Arabic with connected character recognition and RTL layout. |
| LANG-05 | System auto-detects language per page/section | `lingua-language-detector` 2.x with Rust bindings for fast, accurate detection. Use `detect_multiple_languages_of()` for mixed-language text. Store detected language in chunk metadata and Document model. |
| SRH-01 | User can full-text search across all ingested documents | BM25 keyword search via `rank-bm25` library running parallel to ChromaDB. ChromaDB's built-in `where_document={"$contains": ...}` provides basic substring matching. SQLite FTS5 available as fallback for the existing database. |
| SRH-02 | User can semantic search by meaning using vector similarity | ChromaDB `PersistentClient` with `SentenceTransformerEmbeddingFunction` using `paraphrase-multilingual-mpnet-base-v2` (768-dim, 50+ languages including Arabic). Hybrid search combines vector similarity + BM25 keyword via Reciprocal Rank Fusion. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ChromaDB | 1.4.x | Local vector store | Zero-config PersistentClient, built-in sentence-transformers support, metadata filtering, FTS5-based document search. Locked project decision. |
| sentence-transformers | 5.2.x | Embedding model runtime | Load and run `paraphrase-multilingual-mpnet-base-v2` locally. No API costs, offline operation. |
| paraphrase-multilingual-mpnet-base-v2 | - | Multilingual embedding model | 768-dim vectors, 50+ languages including Arabic and English in shared vector space. ~420MB download. |
| rank-bm25 | 0.2.2 | BM25 sparse keyword search | Lightweight BM25Okapi implementation. Needed because ChromaDB's BM25 Search API is cloud-only; local ChromaDB only has `$contains` substring matching. |
| lingua-language-detector | 2.x | Language detection per section | Rust-compiled Python bindings. `detect_multiple_languages_of()` returns per-section language with start/end indices. Accurate on short text and mixed-language content. Supports Arabic. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyArabic | 0.6.x | Arabic text normalization | Strip tashkeel (diacritics), normalize alef variants, normalize lam-alef ligatures. Apply before embedding and indexing. |
| python-bidi | 0.6.x | Bidirectional text algorithm | Apply Unicode BiDi algorithm for correct logical ordering of mixed RTL/LTR text when OCR output has ordering issues. |
| langchain-text-splitters | 0.3.x | Text splitting utilities | `RecursiveCharacterTextSplitter` with custom separators for Arabic (`\n\n`, `\n`, `. `, `\u060C ` [Arabic comma]). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rank-bm25 for BM25 | SQLite FTS5 | FTS5 is built into Python's sqlite3, no extra dependency. But requires separate FTS virtual table setup with aiosqlite, and scoring is less standard than BM25Okapi. Use FTS5 if rank-bm25 memory usage is too high for large corpora. |
| lingua-language-detector | langdetect | langdetect is lighter but non-deterministic and poor on short text. lingua is compiled Rust, fast, and handles mixed-language text with per-section boundaries. |
| lingua-language-detector | fast-langdetect | fast-langdetect is 80x faster (FastText-based) but lacks per-section mixed-language detection. Only use if lingua is too slow. |
| paraphrase-multilingual-mpnet-base-v2 | intfloat/multilingual-e5-large | Higher quality but larger model (~1.1GB vs ~420MB), slower inference. Consider if Arabic retrieval quality is poor with default model. |
| paraphrase-multilingual-mpnet-base-v2 | BAAI/bge-m3 | 8192 token context, hybrid retrieval support. Much larger model. Consider only if 128-token limit is a blocker despite chunking. |
| Custom RRF fusion | LangChain EnsembleRetriever | LangChain provides `EnsembleRetriever` that combines multiple retrievers with RRF. Adds LangChain dependency. Use if we add LangChain anyway for Phase 3. |

**Installation:**
```bash
# Vector database and embeddings
pip install chromadb sentence-transformers

# BM25 keyword search
pip install rank-bm25

# Language detection
pip install lingua-language-detector

# Arabic text processing
pip install PyArabic python-bidi

# Text splitting (optional -- can use custom splitter)
pip install langchain-text-splitters
```

**Note on first-run downloads:** `paraphrase-multilingual-mpnet-base-v2` is ~420MB and downloads from HuggingFace on first use. ChromaDB's default model also downloads on first use. Plan for model pre-download or first-run setup documentation.

## Architecture Patterns

### Recommended Project Structure (New files for Phase 2)

```
app/
├── services/
│   ├── parsing/
│   │   ├── pdf_parser.py          # MODIFY: add "ar" to EasyOCR lang list
│   │   └── ...
│   ├── text_processing/
│   │   ├── __init__.py
│   │   ├── arabic_normalizer.py   # NEW: Arabic text normalization pipeline
│   │   ├── language_detector.py   # NEW: Per-section language detection
│   │   └── text_cleaner.py        # NEW: Post-OCR text cleanup
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── chunking_service.py    # NEW: Semantic document chunking
│   │   ├── embedding_service.py   # NEW: ChromaDB + sentence-transformers
│   │   └── index_manager.py       # NEW: Collection lifecycle management
│   ├── search/
│   │   ├── __init__.py
│   │   ├── vector_search.py       # NEW: ChromaDB semantic search
│   │   ├── keyword_search.py      # NEW: BM25 keyword search
│   │   └── hybrid_search.py       # NEW: RRF fusion of vector + keyword
│   └── document_service.py        # MODIFY: add indexing step after parsing
├── models/
│   ├── document.py                # MODIFY: add language field
│   └── chunk.py                   # NEW: DocumentChunk model (optional, metadata in ChromaDB)
├── schemas/
│   └── search.py                  # NEW: SearchRequest, SearchResult schemas
├── api/
│   └── search.py                  # NEW: Search API endpoints
└── config.py                      # MODIFY: add ChromaDB path, embedding model settings
```

### Pattern 1: Arabic OCR Pipeline Extension

**What:** Extend existing PdfParser to handle Arabic by adding `"ar"` to EasyOCR lang list and applying post-OCR Arabic text normalization.
**When to use:** During document ingestion (modifying existing Phase 1 pipeline).

```python
# app/services/parsing/pdf_parser.py -- MODIFICATION
# Change in _get_converter():
pipeline_options.ocr_options = EasyOcrOptions(
    lang=["en", "ar"],  # Phase 2: Add Arabic
    use_gpu=False,
    force_full_page_ocr=False,
)

# app/services/text_processing/arabic_normalizer.py -- NEW
import re

def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for consistent indexing and search.

    Applies:
    1. Tashkeel (diacritics) removal for matching consistency
    2. Alef variant normalization (hamza forms -> bare alef)
    3. Teh marbuta normalization
    4. Eastern Arabic numeral conversion (٠١٢ -> 012)
    """
    # Remove tashkeel (diacritics: fathatan through sukun)
    text = re.sub(r'[\u064B-\u0652]', '', text)
    # Normalize alef variants to bare alef
    text = re.sub(r'[\u0622\u0623\u0625]', '\u0627', text)
    # Normalize teh marbuta to heh
    text = text.replace('\u0629', '\u0647')
    # Convert Eastern Arabic numerals to Western
    eastern = '٠١٢٣٤٥٦٧٨٩'
    for i, char in enumerate(eastern):
        text = text.replace(char, str(i))
    return text
```

### Pattern 2: Semantic Chunking with Metadata Preservation

**What:** Split parsed documents into chunks that respect semantic boundaries (paragraphs, sections, tables) while preserving source metadata for citations.
**When to use:** After document parsing, before embedding and indexing.

```python
# app/services/indexing/chunking_service.py
from dataclasses import dataclass, field

@dataclass
class DocumentChunk:
    """A chunk of document text with source metadata for citations."""
    chunk_id: str           # Unique ID: "{doc_id}_p{page}_c{chunk_idx}"
    document_id: int        # FK to Document table
    page_number: int        # Source page number
    text: str               # Chunk text content
    text_normalized: str    # Normalized text (Arabic normalization applied)
    language: str           # Detected language: "ar", "en", "mixed"
    section_name: str | None = None  # Detected section heading
    char_start: int = 0     # Character offset in page text
    char_end: int = 0       # Character offset end
    metadata: dict = field(default_factory=dict)

class ChunkingService:
    """Split documents into semantic chunks preserving citation metadata.

    Design decisions:
    - Target ~400 characters per chunk (fits within 128-token limit
      after multilingual tokenization which expands Arabic text)
    - Use paragraph/section boundaries as primary split points
    - Tables are chunked as single units (never split mid-table)
    - Overlap of 50 characters for context continuity
    """

    def __init__(
        self,
        max_chunk_chars: int = 400,
        overlap_chars: int = 50,
    ):
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        # Arabic-aware separators: paragraph, newline, Arabic period,
        # English period, Arabic comma, space
        self.separators = ["\n\n", "\n", "。", ". ", "، ", ", ", " "]

    def chunk_document(
        self,
        document_id: int,
        pages: list,  # list[PageContent]
        filename: str,
    ) -> list[DocumentChunk]:
        chunks = []
        for page in pages:
            # Tables: emit as single chunks (never split)
            for table in page.tables:
                table_text = self._table_to_text(table)
                chunks.append(DocumentChunk(
                    chunk_id=f"{document_id}_p{page.page_number}_t{len(chunks)}",
                    document_id=document_id,
                    page_number=page.page_number,
                    text=table_text,
                    text_normalized=normalize_arabic(table_text),
                    language=detect_language(table_text),
                    section_name=None,
                    metadata={"type": "table", "filename": filename},
                ))

            # Text: split at semantic boundaries
            text_chunks = self._split_text(page.text)
            for i, (text, start, end) in enumerate(text_chunks):
                chunks.append(DocumentChunk(
                    chunk_id=f"{document_id}_p{page.page_number}_c{i}",
                    document_id=document_id,
                    page_number=page.page_number,
                    text=text,
                    text_normalized=normalize_arabic(text),
                    language=detect_language(text),
                    section_name=self._detect_section(text),
                    char_start=start,
                    char_end=end,
                    metadata={"type": "text", "filename": filename},
                ))
        return chunks
```

### Pattern 3: ChromaDB Embedding Service with Multilingual Model

**What:** Initialize ChromaDB PersistentClient with sentence-transformers embedding function, one collection per project.
**When to use:** During document indexing (after chunking) and during search queries.

```python
# app/services/indexing/embedding_service.py
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

class EmbeddingService:
    """Manage ChromaDB collections with multilingual embeddings.

    One collection per project for isolation. Uses
    paraphrase-multilingual-mpnet-base-v2 for Arabic+English
    in a shared vector space.
    """

    def __init__(self, persist_dir: str = "data/chroma"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-mpnet-base-v2",
            device="cpu",  # Set to "cuda" if GPU available
            normalize_embeddings=True,
        )

    def get_collection(self, project_id: int) -> chromadb.Collection:
        """Get or create a collection for a project."""
        return self.client.get_or_create_collection(
            name=f"project_{project_id}",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks(
        self,
        project_id: int,
        chunks: list,  # list[DocumentChunk]
    ) -> None:
        """Add document chunks to the project's vector collection."""
        collection = self.get_collection(project_id)

        # ChromaDB add() accepts batches
        collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text_normalized for c in chunks],
            metadatas=[{
                "document_id": c.document_id,
                "page_number": c.page_number,
                "language": c.language,
                "section_name": c.section_name or "",
                "char_start": c.char_start,
                "char_end": c.char_end,
                **c.metadata,
            } for c in chunks],
        )

    def search_similar(
        self,
        project_id: int,
        query: str,
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        """Semantic search using vector similarity."""
        collection = self.get_collection(project_id)
        return collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
```

### Pattern 4: Hybrid Search with Reciprocal Rank Fusion

**What:** Combine ChromaDB vector similarity search with BM25 keyword search using Reciprocal Rank Fusion.
**When to use:** For all user-facing search queries.

```python
# app/services/search/hybrid_search.py
from dataclasses import dataclass
from rank_bm25 import BM25Okapi

@dataclass
class SearchResult:
    """A single search result with source metadata."""
    chunk_id: str
    text: str
    score: float
    document_id: int
    page_number: int
    language: str
    filename: str

class HybridSearchService:
    """Combines vector (semantic) + BM25 (keyword) search with RRF.

    The alpha parameter controls the weighting:
    - alpha=1.0: pure semantic search
    - alpha=0.0: pure keyword search
    - alpha=0.7: 70% semantic, 30% keyword (recommended default)
    """

    def __init__(
        self,
        embedding_service,      # EmbeddingService instance
        alpha: float = 0.7,     # Weight for semantic search
        rrf_k: int = 60,        # RRF constant (standard value)
    ):
        self.embedding_service = embedding_service
        self.alpha = alpha
        self.rrf_k = rrf_k
        # BM25 indices: one per project, lazily built
        self._bm25_indices: dict[int, tuple] = {}  # project_id -> (bm25, chunk_ids, chunks_data)

    def build_bm25_index(self, project_id: int) -> None:
        """Build BM25 index from all chunks in a project's collection."""
        collection = self.embedding_service.get_collection(project_id)
        results = collection.get(include=["documents", "metadatas"])

        if not results["ids"]:
            return

        # Tokenize documents for BM25
        tokenized = [doc.lower().split() for doc in results["documents"]]
        bm25 = BM25Okapi(tokenized)

        self._bm25_indices[project_id] = (
            bm25,
            results["ids"],
            results["documents"],
            results["metadatas"],
        )

    def search(
        self,
        project_id: int,
        query: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Hybrid search: vector similarity + BM25 keyword, fused with RRF."""
        # 1. Semantic search via ChromaDB
        semantic_results = self.embedding_service.search_similar(
            project_id=project_id,
            query=query,
            n_results=top_k * 3,  # Over-retrieve for fusion
        )

        # 2. BM25 keyword search
        if project_id not in self._bm25_indices:
            self.build_bm25_index(project_id)

        bm25_results = self._bm25_search(project_id, query, top_k * 3)

        # 3. Reciprocal Rank Fusion
        return self._rrf_fusion(
            semantic_results, bm25_results, top_k
        )

    def _rrf_fusion(self, semantic, bm25, top_k):
        """Combine results using Reciprocal Rank Fusion.

        RRF score = sum over retrievers of: weight / (k + rank)
        """
        scores = {}  # chunk_id -> rrf_score
        metadata = {}  # chunk_id -> metadata dict

        # Score semantic results
        for rank, chunk_id in enumerate(semantic["ids"][0]):
            rrf = self.alpha / (self.rrf_k + rank + 1)
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf
            # Store metadata for result construction
            idx = semantic["ids"][0].index(chunk_id)
            metadata[chunk_id] = {
                "text": semantic["documents"][0][idx],
                "metadata": semantic["metadatas"][0][idx],
            }

        # Score BM25 results
        for rank, (chunk_id, text, meta) in enumerate(bm25):
            rrf = (1 - self.alpha) / (self.rrf_k + rank + 1)
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf
            if chunk_id not in metadata:
                metadata[chunk_id] = {"text": text, "metadata": meta}

        # Sort by combined score, return top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for chunk_id, score in ranked:
            meta = metadata[chunk_id]
            results.append(SearchResult(
                chunk_id=chunk_id,
                text=meta["text"],
                score=score,
                document_id=meta["metadata"].get("document_id", 0),
                page_number=meta["metadata"].get("page_number", 0),
                language=meta["metadata"].get("language", "unknown"),
                filename=meta["metadata"].get("filename", ""),
            ))
        return results
```

### Pattern 5: Document Service Integration (Post-Parse Indexing)

**What:** After parsing completes in `process_documents_batch`, automatically chunk and index the document for search.
**When to use:** Extend existing document_service.py to add Phase 2 indexing step.

```python
# Integration point in app/services/document_service.py
# After successful parse, BEFORE marking as completed:

# Phase 2 addition: chunk and index for search
from app.services.indexing.chunking_service import ChunkingService
from app.services.indexing.embedding_service import EmbeddingService

chunking_service = ChunkingService()
embedding_service = EmbeddingService()

chunks = chunking_service.chunk_document(
    document_id=doc_id,
    pages=parsed.pages,
    filename=filename,
)
embedding_service.index_chunks(project_id, chunks)

# Store chunk count in document metadata
doc.metadata_json = json.dumps({
    **parsed.metadata,
    "chunk_count": len(chunks),
    "languages_detected": list(set(c.language for c in chunks)),
}, ensure_ascii=False, default=str)
```

### Anti-Patterns to Avoid

- **Fixed-size chunking (e.g., 1000 chars) ignoring structure:** Splits tables mid-row, separates headings from content. Use semantic boundaries: paragraph breaks, section headings, table boundaries.
- **Embedding full documents instead of chunks:** Exceeds the 128-token limit of the embedding model, causes truncation and lost information. Always chunk first.
- **Indexing raw Arabic text without normalization:** Diacritics and alef variants create duplicate entries for the same word. Normalize before embedding.
- **Using ChromaDB's `$contains` as the sole full-text search:** `$contains` is substring matching, not relevance-ranked. Use BM25 for proper keyword search with TF-IDF scoring.
- **Rebuilding BM25 index on every query:** Build once per project when documents change, cache in memory. Only rebuild when new documents are indexed.
- **Storing embeddings in SQLite:** Use ChromaDB's purpose-built vector index (HNSW). SQLite has no native vector similarity search.
- **One global ChromaDB collection for all projects:** Use one collection per project for isolation and efficient querying. Prevents cross-project leakage and enables per-project deletion.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arabic text normalization | Custom regex for every Arabic character form | PyArabic `strip_tashkeel()` + custom alef/numeral normalization | Arabic has dozens of character forms, ligatures, and combining marks. PyArabic handles edge cases. |
| Language detection per section | Simple regex or character range detection | lingua-language-detector `detect_multiple_languages_of()` | Character-range detection misses transliterated text, numbers. Lingua uses n-gram statistics for accuracy. |
| Vector similarity search | Manual cosine similarity calculation over stored embeddings | ChromaDB `collection.query()` with HNSW index | HNSW provides approximate nearest neighbor search in O(log n), manual brute-force is O(n). |
| BM25 scoring | Custom TF-IDF implementation | rank-bm25 `BM25Okapi` | BM25 has subtle parameter tuning (k1, b constants). Library handles document length normalization correctly. |
| Reciprocal Rank Fusion | Custom score normalization and combination | Standard RRF formula: `1 / (k + rank)` | RRF is score-agnostic (uses ranks only), so it correctly combines BM25 scores and cosine distances without normalization issues. |
| Bidirectional text ordering | Custom Unicode character analysis | python-bidi Unicode BiDi algorithm | The Unicode Bidirectional Algorithm (UBA) is a complex standard with 20+ rules. Do not attempt to implement manually. |
| Sentence/text splitting | Naive `text.split()` or fixed-size slicing | RecursiveCharacterTextSplitter with Arabic-aware separators | Must handle Arabic punctuation (Arabic comma `،`, Arabic semicolon `؛`), paragraph boundaries, and table preservation. |

**Key insight:** Arabic text processing has more edge cases than most developers realize -- character forms change based on position (initial/medial/final/isolated), diacritics are optional but semantically meaningful, and numbers flow LTR within RTL text. Use established libraries rather than building character-level processing.

## Common Pitfalls

### Pitfall 1: Embedding Model 128-Token Truncation
**What goes wrong:** `paraphrase-multilingual-mpnet-base-v2` has a max sequence length of 128 tokens. Arabic text tokenizes into MORE tokens than English (connected script, less efficient tokenization). A 500-character Arabic chunk may exceed 128 tokens and get silently truncated, losing information.
**Why it happens:** The model was trained on short paraphrase pairs. Its tokenizer splits Arabic words into multiple subword tokens.
**How to avoid:** Target chunks of ~400 characters maximum (not 1000). Test actual token counts with the model's tokenizer on Arabic text samples. Monitor for truncation warnings from sentence-transformers.
**Warning signs:** Search quality is poor for longer passages. Arabic results are less relevant than English results for the same concept.

### Pitfall 2: Arabic Number Reordering in Mixed Text
**What goes wrong:** OCR extracts Arabic text with embedded numbers. The logical order in the output has numbers in reversed position or attached to the wrong text segment. "Contract value 1,500,000 SAR" in Arabic might extract with digits reordered.
**Why it happens:** Arabic is RTL but numerals are LTR. OCR engines must detect bidi boundaries correctly. EasyOCR does this better than Tesseract but is not perfect.
**How to avoid:** Post-OCR validation: extract numbers with regex, compare against expected patterns (currency amounts, dates, percentages). Flag suspicious numeric sequences. Store original bounding boxes from OCR for manual verification.
**Warning signs:** Extracted numbers don't match what's visible in the scanned document. Currency values are inconsistent between OCR text and table extraction.

### Pitfall 3: ChromaDB Collection Not Using Correct Embedding Function
**What goes wrong:** Creating a collection without specifying the embedding function, then later querying with a different one. ChromaDB defaults to `all-MiniLM-L6-v2` (384-dim) but our embeddings use `paraphrase-multilingual-mpnet-base-v2` (768-dim). Dimension mismatch causes errors or silently wrong results.
**Why it happens:** ChromaDB stores the embedding function reference at collection creation time. If you `get_collection()` without passing the same embedding function, it may use a different default.
**How to avoid:** ALWAYS pass the `embedding_function` parameter when calling `get_or_create_collection()` and `get_collection()`. Create a single `EmbeddingService` instance that encapsulates the embedding function and collection access.
**Warning signs:** `ValueError: dimension mismatch` errors. Search results are random/irrelevant despite correct indexing.

### Pitfall 4: BM25 Index Stale After New Document Indexing
**What goes wrong:** User uploads new documents, they get embedded into ChromaDB, but the in-memory BM25 index still has the old document set. Keyword searches miss the new documents.
**Why it happens:** BM25 index is built in memory from a snapshot of the collection. It doesn't auto-update when ChromaDB collection changes.
**How to avoid:** Invalidate the BM25 cache for a project whenever new documents are indexed. Rebuild lazily on next search. Store a version counter per project.
**Warning signs:** New documents appear in semantic search but not in keyword search. BM25 results stop changing after initial build.

### Pitfall 5: Chunking Splits Tables or Section Headings from Content
**What goes wrong:** A fixed-size chunker splits a table row in half, or separates a section heading ("Scope of Work") from the paragraphs it introduces. Retrieval returns the heading without context or a partial table row.
**Why it happens:** Fixed-size chunking (which 70% of enterprise RAG systems use) ignores document structure entirely.
**How to avoid:** Chunk tables as single units (even if they exceed max chunk size). Keep section headings attached to the first paragraph of their section. Use `\n\n` (paragraph break) as primary split point, not character count.
**Warning signs:** Retrieved chunks start mid-sentence. Table data appears without headers. Section titles appear alone without content.

### Pitfall 6: Arabic Text Normalization Applied Inconsistently
**What goes wrong:** Documents are indexed with normalized Arabic text (tashkeel removed, alef standardized) but user search queries are NOT normalized. "Ahmed" with hamza doesn't match "Ahmed" without hamza in the index. Or vice versa.
**Why it happens:** Normalization must be applied at BOTH indexing time AND query time. Missing either one breaks exact matching.
**How to avoid:** Create a single `normalize_for_search(text)` function. Apply it in the chunking pipeline (before embedding) AND in the search service (on the query). For BM25, tokenize both index and query through the same normalization.
**Warning signs:** Arabic keyword searches return no results despite the term being present. Same word in different forms doesn't match.

### Pitfall 7: ChromaDB `add()` Duplicate ID Silent Overwrite
**What goes wrong:** Re-indexing a document without first deleting its old chunks causes `add()` to silently overwrite existing chunks with the same IDs. If chunk boundaries change (due to code changes), old chunks with different IDs remain as orphans.
**Why it happens:** ChromaDB's `add()` with existing IDs is a no-op or upsert depending on version. Old chunks from previous parsing are not cleaned up.
**How to avoid:** Before re-indexing a document, delete all chunks for that document from the collection using `collection.delete(where={"document_id": doc_id})`. Then add fresh chunks. Use `upsert()` instead of `add()` for idempotency.
**Warning signs:** Chunk counts grow unexpectedly. Search returns duplicate near-identical results from the same page.

## Code Examples

### EasyOCR Arabic Configuration in Docling

```python
# Source: Docling pipeline_options reference + EasyOCR documentation
# Modify existing _get_converter() in app/services/parsing/pdf_parser.py

from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    EasyOcrOptions,
    TableStructureOptions,
)

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.ocr_options = EasyOcrOptions(
    lang=["en", "ar"],        # English + Arabic
    use_gpu=False,             # Set True if CUDA available
    force_full_page_ocr=False, # Only OCR pages with insufficient text
    confidence_threshold=0.5,  # Minimum OCR confidence (0.0-1.0)
)
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options = TableStructureOptions(
    do_cell_matching=True,
    mode="ACCURATE",
)
```

### Language Detection with Lingua

```python
# Source: lingua-py GitHub + PyPI documentation
from lingua import Language, LanguageDetectorBuilder

# Build detector for expected languages (reduces false positives)
detector = LanguageDetectorBuilder.from_languages(
    Language.ARABIC, Language.ENGLISH
).build()

def detect_language(text: str) -> str:
    """Detect primary language of a text segment."""
    if not text or len(text.strip()) < 10:
        return "unknown"
    lang = detector.detect_language_of(text)
    if lang == Language.ARABIC:
        return "ar"
    elif lang == Language.ENGLISH:
        return "en"
    return "unknown"

def detect_languages_per_section(text: str) -> list[dict]:
    """Detect language boundaries in mixed-language text.

    Returns list of {"language": "ar"|"en", "start": int, "end": int, "text": str}
    """
    results = detector.detect_multiple_languages_of(text)
    sections = []
    for result in results:
        lang_code = "ar" if result.language == Language.ARABIC else "en"
        sections.append({
            "language": lang_code,
            "start": result.start_index,
            "end": result.end_index,
            "text": text[result.start_index:result.end_index],
        })
    return sections
```

### ChromaDB PersistentClient Setup

```python
# Source: ChromaDB docs + cookbook
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

def create_embedding_service(persist_dir: str = "data/chroma"):
    """Create ChromaDB client with multilingual embedding function."""
    client = chromadb.PersistentClient(path=persist_dir)

    ef = SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-mpnet-base-v2",
        device="cpu",
        normalize_embeddings=True,
    )

    return client, ef

# Collection per project:
def get_project_collection(client, ef, project_id: int):
    return client.get_or_create_collection(
        name=f"project_{project_id}",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

# Add chunks:
collection.add(
    ids=["doc1_p1_c0", "doc1_p1_c1"],
    documents=["normalized text chunk 1", "normalized text chunk 2"],
    metadatas=[
        {"document_id": 1, "page_number": 1, "language": "ar", "filename": "tender.pdf"},
        {"document_id": 1, "page_number": 1, "language": "en", "filename": "tender.pdf"},
    ],
)

# Query with metadata filter:
results = collection.query(
    query_texts=["project scope requirements"],
    n_results=10,
    where={"language": "ar"},  # Filter to Arabic chunks only
    include=["documents", "metadatas", "distances"],
)
```

### BM25 Keyword Search with rank-bm25

```python
# Source: rank-bm25 PyPI + common RAG patterns
from rank_bm25 import BM25Okapi

def build_bm25_index(documents: list[str], ids: list[str]):
    """Build BM25 index from document texts.

    Note: rank-bm25 does NO text preprocessing.
    We must normalize and tokenize ourselves.
    """
    # Tokenize: lowercase, split on whitespace
    # Arabic normalization should be applied BEFORE this
    tokenized = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized)
    return bm25, ids

def bm25_search(bm25, ids, query: str, top_k: int = 10):
    """Search BM25 index and return ranked results."""
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Get top-k indices sorted by score
    top_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:top_k]

    return [(ids[i], scores[i]) for i in top_indices if scores[i] > 0]
```

### Search API Endpoint

```python
# app/api/search.py
from fastapi import APIRouter, Depends, Query
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/api/projects/{project_id}/search", tags=["search"])

@router.get("", response_model=SearchResponse)
async def search_documents(
    project_id: int,
    q: str = Query(..., min_length=1, description="Search query"),
    mode: str = Query("hybrid", regex="^(hybrid|semantic|keyword)$"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search across project documents.

    Modes:
    - hybrid: Combined semantic + keyword (default, recommended)
    - semantic: Vector similarity only (find by meaning)
    - keyword: BM25 keyword only (find exact terms)
    """
    # Implementation delegates to HybridSearchService
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tesseract for Arabic OCR | EasyOCR with Arabic lang pack | 2023+ | EasyOCR handles connected Arabic characters and RTL better; ~30% accuracy improvement on Arabic |
| Fixed-size chunking (1000 chars) | Semantic chunking respecting document structure | 2024-2025 | 60% reduction in RAG errors when using semantic boundaries vs fixed-size |
| Vector-only search | Hybrid search (vector + BM25 keyword) | 2024-2025 | "Doubles RAG accuracy" per Microsoft/DeepMind research |
| langdetect for language detection | lingua-language-detector 2.x (Rust bindings) | 2024 | Rust-compiled speed, per-section mixed-language detection, accurate on short text |
| ChromaDB `chroma_db_impl="duckdb+parquet"` | ChromaDB `PersistentClient(path=...)` | 2023 (ChromaDB 0.4+) | Old Settings-based API deprecated. PersistentClient is the current standard. |
| ChromaDB local BM25 | ChromaDB cloud-only Search API with BM25/SPLADE | 2025 | Advanced BM25 is cloud-only. Local users must use rank-bm25 + RRF fusion as workaround. |
| all-MiniLM-L6-v2 (384-dim, English) | paraphrase-multilingual-mpnet-base-v2 (768-dim, 50+ lang) | N/A | Multilingual model required for Arabic+English shared vector space |

**Deprecated/outdated:**
- `chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", ...))`: Removed. Use `chromadb.PersistentClient(path=...)`.
- `collection.add()` without `embedding_function` on `get_or_create_collection()`: Results in dimension mismatches if default model differs.
- `langdetect.detect()` for mixed-language: Non-deterministic, unreliable on short text. Use lingua instead.
- ChromaDB `Search()`, `Knn()`, `Rrf()`, `Schema()` classes locally: These are **cloud-only** as of 2026-02. Use `collection.query()` + external rank-bm25 for local hybrid search.

## Open Questions

1. **Arabic embedding quality on construction tender terminology**
   - What we know: `paraphrase-multilingual-mpnet-base-v2` supports Arabic and places Arabic+English in shared vector space. 128-token max sequence length.
   - What's unclear: How well it handles construction-specific Arabic terms (e.g., concrete specs, BOQ line items). May need testing with real tender documents.
   - Recommendation: Test on sample Arabic tenders early. If retrieval quality is poor, evaluate `intfloat/multilingual-e5-large` (larger but more capable) or `BAAI/bge-m3` (8192 token context).

2. **EasyOCR Arabic accuracy on scanned tender documents**
   - What we know: EasyOCR supports Arabic, handles RTL and mixed scripts. WER of 0.53 on benchmark datasets. Recent KITAB-Bench (2025) shows vision-language models outperform traditional OCR on Arabic.
   - What's unclear: Accuracy on actual construction tender scans (often low-quality photocopies, stamps, handwritten annotations).
   - Recommendation: Test with real scanned Arabic tenders. If accuracy is insufficient, consider Gemini's native document understanding as OCR fallback in Phase 3.

3. **Chunk size optimization for Arabic tokenization**
   - What we know: 128-token limit after multilingual tokenization. Arabic text tokenizes into more subword tokens than English. ~400 chars is estimated safe limit.
   - What's unclear: Exact character-to-token ratio for Arabic construction tender text. May vary by technical vs. general content.
   - Recommendation: Run tokenizer on sample Arabic text to measure exact ratios. Adjust `max_chunk_chars` accordingly. Log truncation events.

4. **BM25 index memory for large projects**
   - What we know: rank-bm25 builds index entirely in memory. Typical tender project might have 500-5000 chunks.
   - What's unclear: Memory footprint for very large projects (50+ documents, 10,000+ chunks).
   - Recommendation: Monitor memory usage. If too large, switch to SQLite FTS5 as a disk-backed alternative for BM25.

5. **Re-indexing workflow when documents are re-parsed**
   - What we know: Phase 1 allows re-uploading documents. ChromaDB needs old chunks deleted before new ones added.
   - What's unclear: Whether to re-index automatically on re-upload or require explicit user action.
   - Recommendation: Auto-delete old chunks for a document before re-indexing. Use `collection.delete(where={"document_id": doc_id})`.

## Sources

### Primary (HIGH confidence)
- [ChromaDB Official Docs - Usage Guide](https://docs.trychroma.com/guides) - PersistentClient, collection API, query API
- [ChromaDB Official Docs - Full Text Search](https://docs.trychroma.com/docs/querying-collections/full-text-search) - `where_document`, `$contains` operator
- [ChromaDB Official Docs - Embedding Functions](https://docs.trychroma.com/docs/embeddings/embedding-functions) - SentenceTransformerEmbeddingFunction
- [ChromaDB Cookbook - Custom Embeddings](https://cookbook.chromadb.dev/embeddings/bring-your-own-embeddings/) - EmbeddingFunction interface
- [ChromaDB Sparse Vector Search announcement](https://www.trychroma.com/project/sparse-vector-search) - BM25/SPLADE support (confirmed cloud-only)
- [ChromaDB Cloud Search API](https://docs.trychroma.com/cloud/search-api/overview) - Confirmed "Search API is available in Chroma Cloud only"
- [Docling Pipeline Options Reference](https://docling-project.github.io/docling/reference/pipeline_options/) - EasyOcrOptions configuration
- [sentence-transformers/paraphrase-multilingual-mpnet-base-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2) - Model card, 128-token limit, 50+ languages
- [EasyOCR GitHub](https://github.com/JaidedAI/EasyOCR) - Arabic support, mixed-script handling
- [lingua-py GitHub](https://github.com/pemistahl/lingua-py) - Per-section mixed-language detection

### Secondary (MEDIUM confidence)
- [KITAB-Bench: Arabic OCR Benchmark (ACL 2025)](https://arxiv.org/html/2502.14949v2) - EasyOCR WER 0.53 on Arabic, modern VLMs outperform
- [rank-bm25 PyPI](https://pypi.org/project/rank-bm25/) - BM25Okapi implementation
- [PyArabic PyPI](https://pypi.org/project/PyArabic/) - Arabic text normalization functions
- [Weaviate: Chunking Strategies for RAG](https://weaviate.io/blog/chunking-strategies-for-rag) - Semantic vs fixed-size chunking
- [Firecrawl: Best Chunking Strategies for RAG 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025) - 400-512 token target
- [Superlinked: Hybrid Search & Reranking](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking) - RRF implementation pattern
- [Microsoft: Vector Search is Not Enough](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/doing-rag-vector-search-is-not-enough/4161073) - Hybrid retrieval doubles accuracy
- [Flitto DataLab: Arabic Text Recognition Challenges](https://datalab.flitto.com/en/company/blog/arabic-text-recognition-challenges-and-solutions/) - RTL-aware OCR 30% improvement

### Tertiary (LOW confidence)
- [python-bidi PyPI](https://pypi.org/project/python-bidi/) - Unicode BiDi algorithm for Python (verify API still current)
- [Stefan Koch: Language Identification in Mixed-Language Texts](https://blog.stefan-koch.name/2024/08/18/lingua-language-identification-mixed-language) - Lingua practical usage
- [HuggingFace Discussion: paraphrase-multilingual 128 token limit](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2/discussions/10) - Increasing max_seq_length possible but untested

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - ChromaDB, sentence-transformers, EasyOCR all verified via official docs. rank-bm25 is well-known. lingua-py verified via GitHub and PyPI.
- Architecture: HIGH - Patterns derived from ChromaDB cookbook, RAG best practices, and existing Phase 1 codebase analysis. Integration points clearly identified.
- Pitfalls: HIGH - Arabic RTL corruption documented in multiple research papers. Embedding truncation verified via HuggingFace model card. ChromaDB cloud-only limitation verified via official docs.
- Code examples: MEDIUM - Based on official docs and common patterns. Some ChromaDB API details (especially around add/upsert behavior) may need validation against installed version.

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days - ChromaDB evolving rapidly, check for local BM25 support release)
