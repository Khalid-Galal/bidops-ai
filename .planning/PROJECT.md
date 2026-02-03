# BidOps AI

## What This Is

A tender document intelligence system that ingests construction project documents (PDFs, Excel BOQs, Word files), extracts structured project metadata with evidence citations, and generates comprehensive bidding requirements checklists. Built for a single estimator/bid manager to dramatically reduce manual tender analysis time.

## Core Value

Extract accurate, citation-backed project summaries and complete requirements checklists from any tender document folder — turning hours of manual review into minutes.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Ingest documents from local Windows folder (PDF, DOCX, XLSX)
- [ ] Parse and index document content with bilingual support (Arabic/English)
- [ ] Build searchable vector index for semantic queries
- [ ] Extract Project Summary with structured fields and evidence citations
- [ ] Generate Bidding Requirements Checklist (Technical/Commercial/Legal/HSE categories)
- [ ] Provide web UI for project setup and results review
- [ ] Run locally as FastAPI backend + browser interface

### Out of Scope

- CAD/Engineering files (DWG, RVT, XER) — complexity, defer to v2
- Cloud folder sources (OneDrive/SharePoint/Google Drive) — local-first for v1
- Multi-user roles and access control — single user for v1
- Email integration — v2 feature
- Supplier management and RFQ distribution — v2 feature
- Offer evaluation and comparison — v2 feature
- BOQ population and pricing — v2 feature
- Indirects calculation — v2 feature
- Mobile app — web-first

## Context

**Domain:** Construction tender/bidding operations in Egypt/MENA region. Documents are typically bilingual (Arabic/English), include ITT packages, specifications, BOQs, contracts, drawings, and addenda.

**Reference codebase:** Existing `bidops-ai/` folder contains a scaffold with FastAPI, SQLAlchemy models, and partial implementations. Starting fresh but using as reference for patterns.

**Codebase map:** Available in `.planning/codebase/` with architecture, stack, and conventions documented.

**User workflow:**
1. Point system at tender folder
2. System ingests and indexes all documents
3. System extracts project summary (name, owner, dates, scope, contract terms, etc.)
4. System generates requirements checklist
5. User reviews, corrects low-confidence extractions
6. Outputs saved for downstream use

## Constraints

- **Platform**: Windows primary (user's work environment)
- **LLM Provider**: Gemini 3 Pro (Google AI)
- **Stack**: Python 3.10+, FastAPI, SQLite, ChromaDB, LangChain
- **Languages**: Must handle Arabic and English equally well (OCR, embeddings, extraction)
- **Offline**: Must work without internet for local files (except LLM API calls)
- **Evidence**: Every extracted value must include source document + page/section citation

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Gemini 3 Pro over GPT-4 | User preference, cost considerations | — Pending |
| Local-first (no cloud folders v1) | Reduce complexity, faster delivery | — Pending |
| Single-user (no auth v1) | Personal tool first, team features later | — Pending |
| Skip CAD parsing v1 | High complexity, low v1 priority | — Pending |
| Fresh build using reference | Existing code is scaffold only, cleaner to rebuild | — Pending |

---
*Last updated: 2026-02-04 after initialization*
