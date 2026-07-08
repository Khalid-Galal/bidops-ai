# BidOps AI — Full System Review & Suggestion Plan

**Date:** 2026-07-07
**Method:** 48-agent multi-dimension review (8 reviewers + adversarial verification of every high/medium finding + live functional testing).
**Result:** 70 confirmed findings (11 high / 28 medium / 31 low), 1 refuted. Functionality verified live: **343/343 tests pass, server boots in ~1s, all pages render, zero contract mismatches between UI and API.**

---

## Executive summary

The system is fundamentally the right build for its purpose — a single-user tendering-operations tool. The architecture (flat FastAPI + services, no speculative layers), the AI design (retrieval-grounded extraction with independent NLI citation verification, structured output via instructor, graceful no-LLM degradation), the formula-preserving pricing writer, and the secret/dependency hygiene were all independently confirmed as correct choices. Nothing is broken today.

The confirmed problems cluster into five themes:

1. **A deployment contradiction (highest risk):** the HF Space is PUBLIC while the README and the whole design assume private. Anyone can read/delete tender data, burn LLM quota, and a stranger's damage gets snapshotted over good backups within ~60s. Fix = flip visibility to private (1 minute).
2. **Reproducibility over time:** requirements are almost entirely unpinned (the build already broke twice from drift), migrations are excluded from the image while the DB outlives the image, and the ~2GB docling/easyocr models are NOT baked despite the stated design.
3. **The AI instruction layer has 4 fixable defects** that explain the two known quality nuances: exact-string citation filename matching (root cause of low-confidence), cross-category dedup + a hard "skip" rule (root cause of submission_documents under-fill), an English-only NLI model that collapses confidence on Arabic tenders, and no temperature/generation config (default ~1.0 for verbatim extraction).
4. **Arabic-market gaps in fields/config:** trade classification keywords are English-only (an Arabic BOQ classifies 0%), 7 spec-listed summary fields are missing (performance bond, LDs, duration, DLP…), ~half of rules.default.json is dead config that silently no-ops, and offer ranking ignores VAT/currency.
5. **Stale tooling:** .planning/ still describes the February v1/legacy tree and would mislead any future GSD session; plan.md (the spec) is not even in git.

---

## Dimension verdicts

| Dimension | Verdict |
|---|---|
| Functionality (live-tested) | **GREEN** — 343/343, clean boot, isolation verified |
| Architecture & structure | **GREEN** — appropriately lazy; residue to delete, no redesign needed |
| UI ↔ API contracts | **GREEN** — zero field-stripping mismatches; second-order JS bugs remain |
| LLM instructions & prompts | **YELLOW** — strong core design, 4 root-cause defects to fix |
| Domain fields & config | **YELLOW** — sound model; missing spec fields + dead config + Arabic gaps |
| Compatibility & deploy | **YELLOW** — works today; unpinned deps + no migration path = time bomb |
| Security & deployment posture | **RED** — public Space contradicts the design; small hardening gaps |
| Dev tooling (.claude/.planning) | **YELLOW** — June-era docs excellent; Feb-era GSD state actively wrong |

---

## Prioritized suggestion plan

### P0 — Do immediately (config-level, minutes)
| # | Action | Why | Effort |
|---|---|---|---|
| 1 | **Flip the HF Space to private** (Settings → Visibility) | World read/write/delete of tender data + supplier contacts, LLM-key burn, destroyed state auto-snapshotted in ~60s. README:55 already mandates private. Private = HF login gate = free auth. | 1 min |
| 2 | Delete the dead leaked Gemini keys from root `.env` and `bidops-ai/.env`; put the future billing-enabled key only in HF Space Secrets + local `.env` | Zero utility, pure liability | 5 min |
| 3 | Wipe stale shakedown data (`data/bidops.db`, `data/chroma`, `data/uploads`) before real use | 5 synthetic tenders will surface as real projects | 5 min |

### P1 — Public-surface hardening (small code, do even if Space goes private)
| # | Action | File | Effort |
|---|---|---|---|
| 4 | Port the offers.py upload pattern (chunked read, size cap → 413, `Path(name).name`) to the main document upload | `app/api/documents.py:106` | ~20 lines |
| 5 | Zip decompressed-size guard: skip members over per-member cap, stop at total budget (use `ZipInfo.file_size`) | `app/services/parsing/zip_parser.py:116` | ~15 lines |
| 6 | Enable rate limiting on the Space (`BIDOPS_RATE_LIMIT_ENABLED=true`) + key buckets on first `x-forwarded-for` hop | `app/middleware.py:133`, Dockerfile ENV | small |
| 7 | Backup: add `revision` param to restore + document rollback; bound dataset growth (squash/retention) | `app/services/backup/backup_service.py:273` | small |

### P2 — Deploy reproducibility (protects every future rebuild)
| # | Action | Why | Effort |
|---|---|---|---|
| 8 | **Commit a Linux lockfile**: build image once, `pip freeze > requirements.lock` inside it, Dockerfile installs from the lock. At minimum pin exactly: chromadb, docling, easyocr, sentence-transformers, torch (`<2.10`) | Dependency drift already broke the build twice; unpinned chromadb can orphan the persisted index; torch 2.10 will break easyocr | small |
| 9 | Pin docling exactly and align the local venv (local runs 2.98.0, Space gets 2.101.0 — tests never exercise the deployed version) | requirements.txt:13 | small |
| 10 | **Ship migrations in the image** (remove `migrations/` + `alembic.ini` from .dockerignore) and run `alembic upgrade head` before create_all; `alembic stamp head` fresh DBs. (Alternative: delete alembic entirely — but the snapshot-restored DB outlives the image, so keeping it is right.) | First schema change after a restore = `no such column` with no in-container fix | small |
| 11 | Bake docling (~2GB) + easyocr models into the image (the "models baked in" design isn't actually done for the heaviest models — every restart re-downloads ~2GB at first PDF ingest) | Dockerfile:46 | small |
| 12 | Enable PDF export on Linux: apt `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fontconfig fonts-dejavu-core fonts-noto-naskh-arabic` (~60MB, no GTK needed) | Recovers a spec feature currently 501 in the container for no reason | small |
| 13 | Hygiene: `.gitattributes` (`*.sh text eol=lf`); fix pyproject build-backend (`setuptools.build_meta`); add explicit `huggingface_hub` + `numpy` to requirements; swap `fastapi[standard]` → `fastapi[standard-no-fastapi-cloud-cli]` | small each |

### P3 — AI extraction quality (the core "instructions & fields" fixes)
| # | Action | Root cause addressed | Effort |
|---|---|---|---|
| 14 | **Citation matching, 3 layers:** (a) match source chunk by normalized verbatim-quote substring FIRST, filename+page as fallback; (b) NFKC/casefold both sides of filename compare; (c) prompt: "copy filename EXACTLY between SOURCE: and \|" + enumerate valid filenames (or per-call `Literal` for document_name). Consolidate the duplicated matcher (checklist_service.py:169) into CitationVerifier. | The known low-confidence fragility (`citation_verifier.py:123`) | medium |
| 15 | **Arabic confidence collapse:** verbatim-quote short-circuit → entailment 1.0 before NLI; swap default NLI model to multilingual (e.g. mDeBERTa-v3-base-xnli) — config field already exists | English-only NLI makes Arabic citations score near-random (empirically confirmed: verbatim Arabic quote scored 0.04) | medium |
| 16 | **submission_documents under-fill, both halves:** dedup within-category only (or submission wins cross-category ties) + add the precedence rule to the prompt: "a document to be SUBMITTED with the bid belongs HERE even if its content is commercial/legal/eligibility" | `checklist_service.py:277` + `context_builder.py:125` | small |
| 17 | Set generation config on all 4 LLM call sites: temperature 0.0–0.2, low thinking budget; expose as Settings | Verbatim-quote fidelity + determinism + free-tier token burn (`gemini_service.py:142`) | small |
| 18 | Fix contract_type enum contradiction ("copy EXACT value" vs snake_case VALID VALUES) → "map to closest VALID VALUE, verbatim wording in the quote"; ideally dynamic `Literal` per enum field | `context_builder.py:76` | small |
| 19 | Bring offer extraction/compliance up to standard: Field descriptions on every schema field, `Literal` for overall_compliance, bounds on compliance_score, null-when-absent + currency/VAT + Arabic guidance in prompts | `offer_extractor.py:31`, `schemas/offer.py:13-43` | medium |

### P4 — Domain fields & Arabic-market completeness
| # | Action | Effort |
|---|---|---|
| 20 | Add missing spec-listed summary fields: performance_bond, liquidated_damages, **project_duration** (feed as default `duration_months` to indirects — currently silently 0), defects_liability_period, insurances, clarification_deadline, main_contractor (+ labels in exports) | medium |
| 21 | **Arabic keywords in config:** every `packaging.trade_categories` list (خرسانة، حديد تسليح، تكييف…) + the 4 uncovered document categories (كراسة الشروط، البرنامج الزمني…). Pure config; without it an Arabic BOQ classifies 0% | small |
| 22 | Arabic terms appended to retrieval queries (field + checklist definitions) + a bilingual prompt line (verbatim source-language quotes) | small |
| 23 | Add `programme` and QAQC checklist categories (plan.md requires them; programme submissions are routinely mandatory) | small |
| 24 | Offer ranking: normalize VAT (vat_included/vat_amount) before price scoring; refuse or loudly flag mixed-currency packages | medium |
| 25 | Comparison workbook: delivery-terms + VAT columns, verbatim exclusions/deviations sheet, optional line-item comparison sheet; add delivery_terms to OfferExtraction | medium |
| 26 | rules.default.json: wire the useful dead keys (required_offer_fields → no-LLM completeness check; quantity_tolerance → matcher; default_validity/payment_terms → prefill) and DELETE the rest from json+schema so every visible knob works. Add `extra="forbid"` to RulesConfig + echo canonical config back into the settings textarea after save | medium |
| 27 | Split `mep` into electrical/mechanical/plumbing/fire_fighting (matches existing abbreviations; real RFQs go out per-discipline); register columns (deadline, est. value, offers received…); optional: historical region field, checklist due_date/notes | small each |

### P5 — UI robustness (all small)
| # | Action | File |
|---|---|---|
| 28 | Fix apostrophe-breaks-Apply bug: numeric-only onclick args, description looked up from a JS map | `_historical.html:45` |
| 29 | Port the fetch+alert download pattern to the 5 native form/link actions (pricing template, indirects template, register, deliverables zip, comparison) so 4xx doesn't dump raw JSON | `_pricing.html`, `_cost.html`, `_packages.html`, `_deliverables.html`, `_offers.html` |
| 30 | `dir="auto"` on tbl() cells + summary/checklist value elements (RTL for Arabic content everywhere, not just search) | `workbench.html:52`, `project.html` |
| 31 | api() helper: stringify non-string 422 detail; OfferResponse.supplier_name; show import row errors; distinct error state vs "not started"; make `!html:` out-of-band (`{html:...}`) | various |

### P6 — Codebase & tooling cleanup
| # | Action | Effort |
|---|---|---|
| 32 | Delete the dead auth cluster: `app/models/user.py`, `audit.py`, UserRole, Supplier.organization, their tests | small |
| 33 | Move the search singleton into the services layer and collapse the 4× copy-pasted LLM/search stack wiring into one accessors module (~90 lines removed; fixes the only api→services inversion) | small |
| 34 | Repo root: **commit plan.md** (it's the spec of record), delete package-lock.json + hs_err_pid*.log + verification_out*, gitignore-or-evict `bidops-ai/`, `.docx`, `.playwright-mcp/` | small |
| 35 | .planning/: archive the v1 milestone, regenerate-or-delete the 7 stale codebase maps (they describe the WRONG tree), or add SUPERSEDED banners to PROJECT/ROADMAP/STATE | small |
| 36 | Add an errata block to the v2 spec (D3 React→Jinja pivot; P15 no-auth) | small |
| 37 | Resolve dual GSD installs (remove project-local v1.20.4 or update it), pick a track/ignore policy for `.claude/`, prune stale settings.local.json permissions, delete new-project.md.bak | small |
| 38 | Micro: templates→pages.py move, trim unreachable enum states, pdf_parser print→logger, misc dedups (only when touching those files) | small |

### Deliberately NOT suggested
- No auth/RBAC build (explicit decision; private Space gives a login gate for free).
- No React SPA revival, no DI/repository layers, no router-prefix refactor for its own sake, no new dependencies where config edits suffice.

---

## Confirmed strengths (what is already the best choice — keep)

- **RAG shape:** per-field/per-category retrieval with `[SOURCE|PAGE]` labels; the LLM only sees retrieved excerpts. Anti-fabrication rules + verbatim-quote requirement + null-when-absent.
- **Independent NLI citation verification** with 3-signal confidence and requires_review — a real anti-hallucination defense, no self-verification bias.
- **Key rotation** fitted exactly to the 8-key free-tier reality; graceful no-LLM degradation honored at every boundary (and verified at the UI layer too).
- **Formula-preserving template writer** (never overwrites `=` cells, two-pass rate-column detect, rejects .xlsm) — precisely the right client-deliverable mechanism.
- **Flat, honest architecture:** thin routers over feature services, pure-ASGI middleware (SSE/downloads unbuffered), in-memory progress store, 62-line rules engine, uniform parser contract that never crashes ingest.
- **Hygiene verified:** no secrets ever committed (full-history search), .dockerignore keeps the image clean, backup dataset private with staged integrity-checked restore, non-root container, offers upload is the model endpoint.
- **UI↔API contracts: zero field-stripping mismatches** — the repo's historical top bug class is now structurally defended.
- **June-era planning docs** (superpowers specs/plans) are accurate, dated, and match the shipped system.

---

## Appendix: full findings register

The complete verified findings (with per-finding verdicts) are preserved in the review digest generated this session. High/medium findings are summarized in the plan above; low findings (31) are quick-win polish items listed in the plan's P5/P6 buckets and the digest.

One finding was **refuted** during verification: "default model gemini-2.5-pro is stale" — the deployed image and local .env both set `BIDOPS_GEMINI_MODEL=gemini-2.5-flash`; the config.py default is an unreached shadow value.
