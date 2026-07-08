# BidOps AI v2 — Design Spec

**Date:** 2026-06-08
**Status:** Approved (roadmap shape + sequence)
**Author:** Claude (brainstorming session with khaled.galal)
**Goal:** Apply the full `plan.md` blueprint to the existing project — extend the working v1 (ingest → summary → checklist → export) into the complete tender-operations platform (packaging → supplier RFQ → offer evaluation → comparison → BOQ pricing → indirects → historical learning → client deliverables).

---

## 1. Context: two codebases

The repo contains **two** code trees (established by an evidence-backed audit on 2026-06-08):

- **Root `app/`** — the GSD v1.0 build. Real, well-structured FastAPI app covering plan.md capabilities **1 (partial), 2, 3 + search + export**. Stack: async SQLAlchemy + aiosqlite, **ChromaDB**, **google-genai + instructor** (Pydantic structured output), **NLI cross-encoder citation verifier** (genuine hallucination defense), Jinja2 server-rendered UI. This is the **authoritative foundation**.
- **`bidops-ai/`** — an earlier, broader scaffold. Contains **real, non-stub** v2-domain code: 7 DB models, ~5,600 lines of services, 4 wired API routers, a full **React SPA**, and a rich `rules.yaml`. Different AI stack (langchain + Qdrant). Used as a **salvage source**, not run as-is.

`plan.md` describes the full vision but v1 deliberately descoped capabilities 4–12 to "v2 deferred." This spec covers building that deferred half.

## 2. Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Build approach | Verify v1 first, then build v2 **incrementally**, all features eventually |
| D2 | Architecture | **Modular FastAPI services** (no CrewAI) |
| D3 | Frontend | **Adopt the React SPA** (`bidops-ai/frontend`, re-pointed to root app's JSON API) |
| D4 | v1 verification | **Full end-to-end run** (synthetic bilingual tender; reuse Gemini key from `bidops-ai/.env`) |
| D5 | Market/locale | **Fully configurable** — no hardcoded currency/VAT/markups/location; neutral defaults + settings UI |
| D6 | Email | **SMTP + mandatory draft-only** preview first; never auto-send without review |
| D7 | Auth/RBAC | **Deferred to Phase 15** — single-user until then (models ported in P6, not enforced) |
| D8 | Rules config | `rules.yaml` → `rules.json` consumed by a `RulesConfig` loader; everything market-configurable |

## 3. Architecture

```
React SPA (bidops-ai/frontend, re-pointed)  ──HTTP/JSON──►  FastAPI (root app/)
   ├─ v1 core (KEEP):  parsing · indexing(ChromaDB) · hybrid search · Gemini+instructor extraction · NLI citation verifier · export
   ├─ v2 domain (PORT): 7 models · pricing_svc · supplier_svc (reuse);  boq · packaging · offer · email · export_svc (adapt)
   ├─ v2 net-new (BUILD): indirects engine · historical-learning engine · formula-preserving template writer · config/rules system
   └─ SQLite (async) · ChromaDB · rules.json
```

**Principle:** every new capability is a focused service module matching v1 patterns (`app/services/<domain>/`, `app/api/<domain>.py`, `app/models/<domain>.py`, `app/schemas/<domain>.py`). LLM calls go through the existing `app/services/llm/gemini_service.py` (instructor + Pydantic). Retrieval/embedding go through existing ChromaDB services.

## 4. Salvage map (from audit — drives effort estimates)

| Source (`bidops-ai/`) | Verdict | Notes |
|---|---|---|
| 7 models (boq, package, supplier+SupplierOffer, email, audit, user/org) | **Reuse** | Same async SQLAlchemy 2.0 idiom; re-base on `app.database.Base` |
| `pricing_service`, `supplier_service` | **Reuse** | Pure-Python/DB-only; no LLM/vector coupling |
| `rules.yaml`, XER parser, EML parser | **Reuse** | Framework-agnostic; rules de-UAE'd to neutral defaults |
| `boq`/`packaging`/`offer`/`email`/`export` services | **Adapt** | Rework `generate(json_mode)+json.loads` → instructor Pydantic; Qdrant → ChromaDB; reportlab → weasyprint |
| 4 API routers, React pages, CAD/PPTX/MSG/image parsers | **Adapt** | Re-point to root API contract; provision optional deps (ezdxf, pytesseract, etc.) |
| `extraction`/`llm`/`vector_store` services | **Rebuild** | v1 already does these better (instructor + ChromaDB + NLI) |
| Indirects, historical learning, formula-preserving population, MS-Graph email, audit-write path | **Net-new** | Absent or only partial anywhere |

## 5. v1 verification (Phase 0) — bugs to fix

Found by audit; fix as part of "verify v1 works":
1. **Excel export checkbox state** — `VerifiedRequirement` drops the `checked` key on parse, so exported Status is always "Unchecked." Fix: add `checked: bool = False` to the schema (round-trips) or read from raw `checklist_json`.
2. **Eligibility skip-list mismatch** — prompt skip-list uses literal `"Eligibility"` but display_name is `"Eligibility / Pre-Qualification"`, telling the LLM to skip the category it's extracting. Fix: align the string.
3. **BM25 stale index** — ingest path never calls `invalidate_keyword_index()` after indexing. Fix: invoke it in `document_service.process_documents_batch` after `index_chunks`.

Also: establish a reproducible venv run, set `BIDOPS_GEMINI_API_KEY`, run a synthetic bilingual tender through ingest→summary→checklist→export with evidence.

## 6. Roadmap (each phase = its own plan → build → verify cycle)

- **Phase 0 — Verify v1 + fix bugs** *(in progress)*
- **Phase 6 — Foundation**: port 7 models + alembic migration; configurable **rules/market system**; stand up **React SPA** on v1 JSON API + wire existing v1 features. *(single-user)*
- **Phase 7 — Ingestion expansion** (cap 1): TXT/EML/MSG/PPTX/image-OCR/ZIP/XER/CAD parsers; BOQ Excel parsing + trade classification; doc classification + addenda-supersedes versioning + dedup.
- **Phase 8 — BOQ Packaging** (caps 4, 6): trade packages, semantic doc→item linking, package folders, Package Brief PDF, Packages Register.xlsx, BOQ subset + React pages.
- **Phase 9 — Suppliers + RFQ email** (cap 5): supplier DB + Excel import/export, **SMTP draft-only** bilingual RFQ + mandatory preview, email log.
- **Phase 10 — Offer evaluation + comparison** (caps 7, 8): offer ingest, compliance vs checklist, configurable weighted scoring + ranking, clarification-email drafts, comparison-matrix Excel.
- **Phase 11 — BOQ pricing** (cap 9): price population from selected offers (fuzzy+semantic mapping), markups, gaps/risk report, **formula-preserving** client-template population.
- **Phase 12 — Indirects** (cap 10) — net-new.
- **Phase 13 — Historical learning** (cap 11) — net-new: index historical sheets, suggest prices/benchmarks with traceability + correction feedback.
- **Phase 14 — Deliverables + dashboard** (cap 12).
- **Phase 15 — NFRs** (last/optional): auth/RBAC + audit-trail write path, credential encryption, reliability (retries/incremental indexing), test suite.

## 7. Out of scope (this milestone)

- CrewAI / multi-agent rearchitecture (explicitly rejected — D2).
- Cloud folder sources (OneDrive/SharePoint/Google Drive) — local-first.
- Revit RVT/IFC and Navisworks NWD parsing (CAD DXF/DWG only via ezdxf + ODA).
- Microsoft Graph email (SMTP only this milestone — D6).
- Auto-submission of bids.

## 8. Non-functional notes

- **Tests**: v1 has zero automated tests. Each new phase adds pytest coverage for its pure-logic units (mock LLM/embedding/vector boundaries). Test scaffolding established in P6.
- **Reliability/security NFRs** consolidated into P15 to avoid blocking core automation.
- **Windows-first**: weasyprint needs native Pango (PDF export degrades to HTTP 501 if absent); Tesseract binary needed for image OCR.

## 9. Errata

**D3 (Frontend) — Pivoted to Jinja Server-Rendered**
Initially approved as "React SPA (bidops-ai/frontend, re-pointed to root app's JSON API)." The shipped system pivoted to Jinja2 server-rendered templates at the root `app/` level. Rationale: simpler stack for single-user desktop tool, faster server-side rendering, avoids React SPA complexity and build overhead.

**P15 (Auth/RBAC) — Shipped without auth by explicit decision**
Phase 15 was deferred as stated (line 77), marking auth/RBAC as "last/optional." The shipped v1 system intentionally omitted authentication enforcement, suitable for single-user local deployment. Auth models were ported in P6 (structured) but not enforced in runtime, preserving works-without-key degradation guarantee and local-first design.

---

*Each phase will be planned in detail (its own plan doc) immediately before execution, following the project's established GSD `.planning/` workflow.*
