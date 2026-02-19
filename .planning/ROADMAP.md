# Roadmap: BidOps AI

## Overview

BidOps AI transforms construction tender document folders into structured, citation-backed project summaries and requirements checklists. The roadmap builds capabilities in dependency order: first ingest documents reliably across formats, then handle bilingual content and enable search, then extract structured data with LLM-powered intelligence (summary first, then checklist), and finally deliver a complete review and export workflow through the web interface.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Document Ingestion Pipeline** - Parse PDF/DOCX/XLSX tender documents into clean structured content
- [x] **Phase 2: Bilingual Processing & Search** - Handle Arabic/English content and enable document search
- [ ] **Phase 3: Project Summary Extraction** - Extract citation-backed project metadata using LLM
- [ ] **Phase 4: Requirements Checklist Extraction** - Generate categorized requirements checklist from tender documents
- [ ] **Phase 5: Results Interface & Export** - Complete web UI for reviewing, editing, searching, and exporting results

## Phase Details

### Phase 1: Document Ingestion Pipeline
**Goal**: User can upload any tender document set and get clean, parsed content with preserved structure
**Depends on**: Nothing (first phase)
**Requirements**: UI-05, UI-01, ING-01, ING-02, ING-03, ING-04, ING-05, LANG-02
**Success Criteria** (what must be TRUE):
  1. User can start the FastAPI server and access a web interface in the browser
  2. User can create a new project and upload a folder of mixed PDF/DOCX/XLSX files through the web interface
  3. User can see processing progress while documents are being parsed
  4. System correctly extracts text, tables, and structure from native PDFs, scanned PDFs (via OCR), Word documents, and Excel spreadsheets
  5. Parsed content preserves page numbers, section boundaries, and table structure for downstream citation use
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — FastAPI application scaffold with database, project/document models, and project CRUD API
- [x] 01-02-PLAN.md — Multi-format document parsing pipeline (PDF/DOCX with Docling, XLSX with openpyxl)
- [x] 01-03-PLAN.md — Document upload API, processing service, SSE progress streaming, and web UI

### Phase 2: Bilingual Processing & Search
**Goal**: User can search across bilingual tender documents by keyword or meaning, with Arabic content handled correctly
**Depends on**: Phase 1
**Requirements**: LANG-01, LANG-03, LANG-04, LANG-05, SRH-01, SRH-02
**Success Criteria** (what must be TRUE):
  1. System correctly processes Arabic text with proper RTL rendering and no character corruption
  2. System handles mixed Arabic/English pages without scrambling text order or corrupting numbers
  3. System performs OCR on scanned Arabic documents and produces accurate text
  4. User can search across all ingested documents by keyword (full-text) and find exact matches
  5. User can search by meaning (semantic search) and find conceptually related content across languages
**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Arabic OCR pipeline with EasyOCR, Arabic text normalization (PyArabic), and per-section language detection (lingua)
- [x] 02-02-PLAN.md — Semantic document chunking and ChromaDB vector indexing with multilingual embeddings (paraphrase-multilingual-mpnet-base-v2)
- [x] 02-03-PLAN.md — Hybrid search API combining BM25 keyword search (rank-bm25) and vector similarity with RRF fusion

### Phase 3: Project Summary Extraction
**Goal**: User receives a complete, citation-backed project summary extracted from tender documents with confidence indicators
**Depends on**: Phase 2
**Requirements**: SUM-01, SUM-02, SUM-03, SUM-04, SUM-05, SUM-06, CIT-01, CIT-02, CIT-03, CIT-04
**Success Criteria** (what must be TRUE):
  1. User receives extracted project name, owner, location, scope of work, contract type, key dates, financial terms, and stakeholder list from uploaded tender documents
  2. Every extracted value shows the source document name and page number where it was found
  3. User can view the exact quote from the source document that supports each extracted value
  4. Each extraction displays a confidence score (high/medium/low) indicating reliability
  5. Low-confidence extractions are visually flagged so the user knows which items need manual review
**Plans:** 3 plans

Plans:
- [ ] 03-01-PLAN.md — LLM service integration (Gemini + instructor), Pydantic extraction schemas, field definitions with query hints, and config updates
- [ ] 03-02-PLAN.md — NLI citation verification with cross-encoder model and calibrated confidence scoring
- [ ] 03-03-PLAN.md — Extraction pipeline orchestration with per-field retrieval, API endpoint, and database persistence

### Phase 4: Requirements Checklist Extraction
**Goal**: User receives a categorized, evidence-backed requirements checklist covering all tender obligations
**Depends on**: Phase 3
**Requirements**: CHK-01, CHK-02, CHK-03, CHK-04, CHK-05, CHK-06, CHK-07
**Success Criteria** (what must be TRUE):
  1. System extracts technical, commercial, legal, and HSE requirements from tender documents into a structured checklist
  2. Each requirement in the checklist is categorized by type (Technical/Commercial/Legal/HSE)
  3. System identifies and lists all mandatory submission documents required by the tender
  4. System detects eligibility and pre-qualification criteria and surfaces them prominently
  5. Each checklist item carries citation and confidence data (using the infrastructure from Phase 3)
**Plans**: TBD

Plans:
- [ ] 04-01: Requirements extraction pipeline with category-specific prompts and schemas
- [ ] 04-02: Mandatory documents detection and eligibility/pre-qualification criteria extraction
- [ ] 04-03: Checklist assembly with categorization, citation linking, and confidence scoring

### Phase 5: Results Interface & Export
**Goal**: User can review, edit, search, and export all extracted data through a complete web interface
**Depends on**: Phase 4
**Requirements**: UI-02, UI-03, UI-04, EXP-01, EXP-02
**Success Criteria** (what must be TRUE):
  1. User can view the full project summary with all extracted fields in the web interface
  2. User can view, check off, and edit items in the requirements checklist through the web interface
  3. User can search documents from the web interface and see results with context
  4. User can export the project summary and checklist to an Excel file
  5. User can export a formatted report to PDF with citation appendix
**Plans**: TBD

Plans:
- [ ] 05-01: Project summary and checklist review UI with inline editing
- [ ] 05-02: Document search UI with result highlighting and context display
- [ ] 05-03: Export service for Excel and PDF output with citation appendix

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Document Ingestion Pipeline | 3/3 | Complete | 2026-02-19 |
| 2. Bilingual Processing & Search | 3/3 | Complete | 2026-02-19 |
| 3. Project Summary Extraction | 0/3 | Not started | - |
| 4. Requirements Checklist Extraction | 0/3 | Not started | - |
| 5. Results Interface & Export | 0/3 | Not started | - |
