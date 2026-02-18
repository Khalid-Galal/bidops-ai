# BidOps AI -- Requirements

**Version:** v1.0
**Date:** 2026-02-04
**Status:** Approved

---

## v1 Requirements

### Document Ingestion

- [ ] **ING-01**: User can upload and parse PDF documents including scanned PDFs via OCR
- [ ] **ING-02**: User can upload and parse Word (DOCX) documents
- [ ] **ING-03**: User can upload and parse Excel (XLSX) files (BOQ, pricing sheets)
- [ ] **ING-04**: User can batch upload an entire folder of documents at once
- [ ] **ING-05**: User sees progress indication during document processing

### Language Processing

- [ ] **LANG-01**: System handles Arabic text correctly with RTL support
- [ ] **LANG-02**: System handles English text correctly
- [ ] **LANG-03**: System handles mixed Arabic/English documents on the same page
- [ ] **LANG-04**: System performs Arabic OCR on scanned Arabic documents
- [ ] **LANG-05**: System auto-detects language per page/section

### Project Summary Extraction

- [ ] **SUM-01**: User receives extracted project name, owner, and location
- [ ] **SUM-02**: User receives key dates (submission deadline, validity, pre-bid meeting)
- [ ] **SUM-03**: User receives scope of work summary
- [ ] **SUM-04**: User receives contract type (lump sum, remeasured, etc.)
- [ ] **SUM-05**: User receives financial terms (tender bond, advance %, retention %, payment terms)
- [ ] **SUM-06**: User receives stakeholder list (consultants, PMC, designer)

### Requirements Checklist

- [ ] **CHK-01**: System extracts technical requirements from tender documents
- [ ] **CHK-02**: System extracts commercial requirements
- [ ] **CHK-03**: System extracts legal requirements
- [ ] **CHK-04**: System extracts HSE requirements
- [ ] **CHK-05**: System categorizes requirements by type (Technical/Commercial/Legal/HSE)
- [ ] **CHK-06**: System extracts mandatory submission documents list
- [ ] **CHK-07**: System detects eligibility/pre-qualification criteria

### Evidence & Citations

- [ ] **CIT-01**: Every extracted value links to source document and page number
- [ ] **CIT-02**: User can see exact quote from source document for each extraction
- [ ] **CIT-03**: System assigns confidence scores (high/medium/low) to each extraction
- [ ] **CIT-04**: System flags low-confidence items for human review

### Search

- [ ] **SRH-01**: User can full-text search across all ingested documents
- [ ] **SRH-02**: User can semantic search by meaning using vector similarity

### Export

- [ ] **EXP-01**: User can export checklists and summaries to Excel
- [ ] **EXP-02**: User can export formatted reports to PDF

### UI & Platform

- [ ] **UI-01**: User can create projects and upload documents via web interface
- [ ] **UI-02**: User can view project summaries in the web interface
- [ ] **UI-03**: User can view and edit requirements checklists in the web interface
- [ ] **UI-04**: User can search documents from the web interface
- [ ] **UI-05**: System runs as local FastAPI backend with browser-based UI

---

## v2 Requirements (Deferred)

- CAD/DWG file parsing and drawing analysis
- Email integration and supplier RFQ distribution
- Offer evaluation and comparison matrices
- BOQ population and pricing automation
- Indirects calculation from historical data
- Multi-user roles and access control
- Cloud deployment and team access
- Package creation from BOQ items
- Supplier database management

---

## Out of Scope

- Auto-submission of bids -- too risky, human approval required
- Generic chat interface -- structured extraction, not conversation
- Complex pricing/estimation -- different domain, use export for integration
- Mobile-first design -- desktop activity, responsive sufficient
- Tender discovery/marketplace -- separate product
- Real-time collaborative editing -- overkill for v1 single-user

---

## Traceability

| REQ-ID | Phase | Plan | Status |
|--------|-------|------|--------|
| ING-01 | Phase 1 | -- | Pending |
| ING-02 | Phase 1 | -- | Pending |
| ING-03 | Phase 1 | -- | Pending |
| ING-04 | Phase 1 | -- | Pending |
| ING-05 | Phase 1 | -- | Pending |
| LANG-01 | Phase 2 | -- | Pending |
| LANG-02 | Phase 1 | -- | Pending |
| LANG-03 | Phase 2 | -- | Pending |
| LANG-04 | Phase 2 | -- | Pending |
| LANG-05 | Phase 2 | -- | Pending |
| SUM-01 | Phase 3 | -- | Pending |
| SUM-02 | Phase 3 | -- | Pending |
| SUM-03 | Phase 3 | -- | Pending |
| SUM-04 | Phase 3 | -- | Pending |
| SUM-05 | Phase 3 | -- | Pending |
| SUM-06 | Phase 3 | -- | Pending |
| CHK-01 | Phase 4 | -- | Pending |
| CHK-02 | Phase 4 | -- | Pending |
| CHK-03 | Phase 4 | -- | Pending |
| CHK-04 | Phase 4 | -- | Pending |
| CHK-05 | Phase 4 | -- | Pending |
| CHK-06 | Phase 4 | -- | Pending |
| CHK-07 | Phase 4 | -- | Pending |
| CIT-01 | Phase 3 | -- | Pending |
| CIT-02 | Phase 3 | -- | Pending |
| CIT-03 | Phase 3 | -- | Pending |
| CIT-04 | Phase 3 | -- | Pending |
| SRH-01 | Phase 2 | -- | Pending |
| SRH-02 | Phase 2 | -- | Pending |
| EXP-01 | Phase 5 | -- | Pending |
| EXP-02 | Phase 5 | -- | Pending |
| UI-01 | Phase 1 | -- | Pending |
| UI-02 | Phase 5 | -- | Pending |
| UI-03 | Phase 5 | -- | Pending |
| UI-04 | Phase 5 | -- | Pending |
| UI-05 | Phase 1 | -- | Pending |

---
*Last updated: 2026-02-18 after roadmap creation*
