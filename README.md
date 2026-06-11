---
title: BidOps AI
emoji: 📑
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# BidOps AI

An AI-assisted tender-operations platform: ingest tender documents, extract a
cited summary + requirements checklist, parse and classify the BOQ, build trade
packages, draft supplier RFQ emails, evaluate offers, price the BOQ (formula-
preserving), roll up indirects and total cost, benchmark against a historical
corpus, and assemble a client-ready deliverables bundle — with a server-rendered
workbench UI.

## Running on Hugging Face (Docker Space)

This Space is built from the `Dockerfile`. The app listens on port **7860** and
bootstraps its SQLite schema on startup.

### Required configuration (Settings → Variables and secrets)

| Kind | Name | Value |
|---|---|---|
| **Secret** | `BIDOPS_GEMINI_API_KEYS` | comma-separated Gemini API key(s) — enables the AI features |
| Variable | `BIDOPS_GEMINI_MODEL` | `gemini-2.5-flash` (already defaulted in the image) |
| **Secret** | `HF_TOKEN` | HF **write** token — enables free snapshot persistence (below) |
| Variable | `BIDOPS_BACKUP_DATASET_REPO` | e.g. `<user>/bidops-data` — private dataset repo for snapshots |

### Free snapshot persistence (no paid disk needed)

When `HF_TOKEN` + `BIDOPS_BACKUP_DATASET_REPO` are set, the app snapshots its
state (database, uploads, offer files, vector index, rules override) to that
**private** HF Dataset repo whenever data changes (~every 60s), and restores
the latest snapshot automatically on a fresh boot — so projects survive
rebuilds, restarts, and Space sleep. The repo is auto-created on first backup.
Regenerable artifacts (`packages/`, `deliverables/`) are excluded; re-run their
export/build endpoints after a restore. Manual trigger: `POST /api/backup`;
state: `GET /api/backup/status`.

Without a Gemini key the deterministic pipeline (BOQ parsing, packaging, pricing,
indirects, historical benchmarks, deliverables, RFQ/clarification drafts) works
fully; only the LLM steps (summary extraction, checklist, offer extraction /
compliance) return 503.

### Notes

- **Storage is ephemeral**: the database, uploads, and vector index reset on each
  restart/rebuild. Enable HF persistent storage and point the data dir at `/data`
  to keep them.
- **No authentication**: keep this Space **private** — it carries your API keys and
  has no login.
- Email **sending** needs SMTP creds (`BIDOPS_SMTP_HOST/USER/PASSWORD`); drafts and
  preview work without them. **PDF** export needs GTK (not installed); Excel works.

## Local run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

Health: `GET /health` (liveness) · `GET /ready` (DB + model-warm).
