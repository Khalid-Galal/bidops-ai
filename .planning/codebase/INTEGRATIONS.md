# External Integrations

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-03

## APIs & External Services

**LLM/AI:**
- Google Gemini API - Primary LLM provider for document analysis and extraction
  - SDK/Client: `langchain-google-genai` 2.0.8+, `google-generativeai` 0.8.3+
  - Models: Gemini 2.5 Flash (simple/moderate tasks), Gemini 2.5 Pro (complex tasks)
  - Auth: `GOOGLE_API_KEY` environment variable
  - Usage location: `app/services/llm_service.py` with task-based routing

- OpenAI (Optional) - Fallback LLM and embedding provider
  - SDK/Client: `langchain-openai` 0.1.0
  - Models: GPT-4o for generation, text-embedding-3-small for embeddings
  - Auth: `OPENAI_API_KEY` environment variable
  - Usage location: `app/services/vector_store.py` for embeddings

**Email:**
- SMTP (Gmail, Office365, custom servers) - RFQ and notification email sending
  - Provider config: `EMAIL_PROVIDER` environment variable (default: "smtp")
  - Auth: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
  - From address: `SMTP_FROM`
  - Usage location: `app/services/email_service.py`
  - Features: HTML email templates, attachments, RFQ formatting, reminder emails

- Microsoft Graph API (Optional) - Outlook/OneDrive integration
  - SDK/Client: `msgraph-sdk` 1.2.0, `msal` 1.26.0
  - Auth: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
  - Provider: `EMAIL_PROVIDER=graph` in configuration
  - Features: Outlook inbox integration, OneDrive document access
  - Usage location: `app/services/email_service.py`

## Data Storage

**Databases:**
- PostgreSQL 16 (production)
  - Connection: `DATABASE_URL=postgresql+asyncpg://...`
  - Client: SQLAlchemy 2.0.25+ with asyncpg 0.29.0 driver
  - Models location: `app/models/` (user, project, document, package, supplier, offer, etc.)
  - Migrations: Alembic (`backend/migrations/`) for schema versioning

- SQLite (development/local testing)
  - Connection: `sqlite+aiosqlite:///./storage/database/bidops.db`
  - Client: SQLAlchemy with aiosqlite 0.19.0 driver
  - Default location: `storage/database/`

**Vector Database:**
- Qdrant (semantic search and embeddings)
  - Connection: `QDRANT_URL=http://localhost:6333`
  - Collection: `QDRANT_COLLECTION=bidops_documents`
  - Embedding dimensions: 1536 (OpenAI text-embedding-3-small compatibility)
  - Client: `qdrant-client` 1.7.0+
  - Embeddings source: Google Gemini or sentence-transformers (fallback)
  - Usage location: `app/services/vector_store.py` for semantic search

**Caching & Message Queue:**
- Redis 7
  - Connection: `REDIS_URL=redis://localhost:6379`
  - Purpose: Caching and task queue backend
  - Task queue: arq 0.25.0 for background jobs
  - Usage location: `app/worker.py` for background document processing

**File Storage:**
- Local filesystem only (no cloud storage integration)
  - Project files: `PROJECTS_PATH=./storage/projects`
  - Temporary files: `TEMP_PATH=./storage/temp`
  - Database files: `DATABASE_PATH=./storage/database`
  - Max upload size: `MAX_UPLOAD_SIZE_MB=500`

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based authentication (custom implementation)
  - Implementation: `app/auth/jwt.py`, `app/auth/password.py`
  - Token type: JWT with HS256 algorithm
  - Auth env vars: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=7`
  - Password hashing: bcrypt via passlib
  - Usage location: `app/api/v1/auth.py` endpoints

**Azure/Microsoft Identity (Optional):**
- Azure Active Directory authentication for Graph API access
  - Env vars: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
  - Auth library: msal 1.26.0
  - Purpose: Outlook/OneDrive integration via Microsoft Graph

## Monitoring & Observability

**Error Tracking:**
- Not detected - No third-party error tracking service configured
- Application exception handling in place at `app/main.py` with custom handlers
- Structured logging via `structlog` 24.1.0

**Logs:**
- Structured logging approach using `structlog` 24.1.0
- Console output in development
- No centralized log aggregation detected

## CI/CD & Deployment

**Hosting:**
- Render.com - Primary deployment platform
  - Config: `render.yaml`, `Dockerfile.railway`
  - Environment file: `.env.render`
  - Health check endpoint: `/api/v1/health`

- Railway.app - Secondary deployment option
  - Config: `railway.json`
  - Dockerfile: `Dockerfile.railway`
  - Documentation: `RAILWAY_DEPLOY.md`

- Fly.io - Deployment option
  - Config: `fly.toml` in backend directory
  - Documentation: `FLY_DEPLOY.md`

- Vercel - Frontend deployment option
  - Config: `vercel.json`
  - Documentation: `VERCEL_DEPLOY.md`

**CI Pipeline:**
- GitHub Actions (workflow definitions in `.github/`)
- Not fully configured in this analysis; integration tests via Playwright

## Environment Configuration

**Required env vars:**
- `GOOGLE_API_KEY` - Google Gemini API access (critical for LLM features)
- `SECRET_KEY` - JWT signing secret (must be strong in production)
- `DATABASE_URL` - PostgreSQL or SQLite connection string
- `REDIS_URL` - Redis connection for caching/tasks
- `QDRANT_URL` - Vector database URL
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email sending

**Optional env vars:**
- `OPENAI_API_KEY` - OpenAI for fallback LLM/embeddings
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` - Graph API access
- `OLLAMA_URL` - Local LLM support (default: `http://localhost:11434`)
- `ODA_CONVERTER_PATH` - Windows CAD file converter path
- `TESSERACT_CMD` - OCR binary location

**Secrets location:**
- `.env` file (development, git-ignored)
- Environment variables in deployment platforms (Render, Railway, Fly.io)
- Render: Service-specific env vars
- No vault/secrets manager detected

## Webhooks & Callbacks

**Incoming:**
- Not detected - No webhook endpoints for external services

**Outgoing:**
- Email notifications via SMTP (RFQ emails, reminders)
- No outbound webhooks to third-party services detected

## Data Sync & Polling

**Background Jobs:**
- Task queue via Redis + ARQ
- Worker process: `app/worker.py` with `WorkerSettings` configuration
- Job types likely include:
  - Document processing and embedding
  - Email sending
  - Report generation/export
  - Vector store operations

## Rate Limiting & Quotas

**API Rate Limiting:**
- Not explicitly configured (FastAPI has no rate limiting middleware detected)
- Should be implemented based on usage patterns

**Service Quotas:**
- Google Gemini API quotas apply
- PostgreSQL/Redis connection pool limits in SQLAlchemy config
- Vector database storage limits based on Qdrant instance size

---

*Integration audit: 2026-02-03*
