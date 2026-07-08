# Technology Stack

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-03

## Languages

**Primary:**
- Python 3.11+ - Backend API, services, document processing, data processing
- TypeScript 5.3.3 - Frontend React application, type-safe UI code
- JavaScript - Build tooling, E2E test scripts, Node utilities

**Secondary:**
- YAML - Configuration files (`config/rules.yaml`)
- SQL - Database queries via SQLAlchemy ORM

## Runtime

**Environment:**
- Python 3.11+ runtime for backend API and worker processes
- Node.js 18+ for frontend build and E2E tests
- Docker containers for isolated service deployment

**Package Manager:**
- pip - Python dependency management (backend)
- npm - Node.js package management (frontend, E2E tests)
- Lockfile: `package-lock.json` present for frontend

## Frameworks

**Core:**
- FastAPI 0.109.0+ - Backend REST API framework, async request handling
- React 18.2.0 - Frontend SPA framework
- Vite 5.0.12 - Frontend bundler and dev server

**Testing:**
- Playwright 1.48.0 - E2E browser testing (`e2e-tests/` directory)
- pytest (optional, commented out in requirements) - Backend unit testing

**Build/Dev:**
- TypeScript 5.3.3 - Type checking
- ESLint 8.56.0 - Frontend code linting
- Tailwind CSS 3.4.1 - Utility-first CSS framework
- PostCSS 8.4.33 - CSS processing pipeline
- Autoprefixer 10.4.17 - Browser vendor prefixes

## Key Dependencies

**Critical:**
- FastAPI 0.109.0+ - Web framework, dependency injection, request validation
- SQLAlchemy 2.0.25+ with asyncio - Database ORM supporting PostgreSQL and SQLite
- Pydantic 2.5.0+ - Data validation and serialization
- google-generativeai 0.8.3+ - Google Gemini API client for LLM features
- langchain 0.2.0+ with langchain-google-genai - AI/LLM orchestration
- qdrant-client 1.7.0+ - Vector database client for semantic search
- redis 5.0.0 - Caching and task queue backend
- arq 0.25.0 - Async task queue for background jobs

**Infrastructure:**
- asyncpg 0.29.0 - PostgreSQL async driver
- aiosqlite 0.19.0 - SQLite async driver for development
- uvicorn[standard] 0.27.0 - ASGI server
- Pillow 10.2.0 - Image processing (document OCR support)

**Document Processing:**
- pymupdf (fitz) 1.23.0 - PDF parsing and text extraction
- pdf2image 1.17.0 - PDF to image conversion
- pytesseract 0.3.10 - OCR for scanned documents
- python-docx 1.1.0 - DOCX file parsing
- python-pptx 0.6.23 - PPTX presentation parsing
- openpyxl 3.1.2 - XLSX spreadsheet parsing
- pandas 2.2.0 - Data analysis and manipulation
- extract-msg 0.48.0 - MSG email file parsing
- mail-parser 3.15.0 - Email message parsing
- ezdxf 1.1.1 - DXF/CAD file parsing

**AI/LLM:**
- langchain 0.2.0+ - LLM framework for prompt management, chains
- langchain-community 0.2.0 - Community integrations
- langchain-openai 0.1.0 - OpenAI integration support
- langgraph 0.1.0 - Agentic workflows
- sentence-transformers 2.3.0 - Local embeddings fallback

**Authentication & Security:**
- python-jose[cryptography] 3.3.0 - JWT token creation/validation
- passlib[bcrypt] 1.7.4 - Password hashing
- cryptography 42.0.0 - Cryptographic operations
- python-multipart 0.0.6 - Multipart form data parsing

**Microsoft Integration:**
- msal 1.26.0 - Microsoft Azure authentication
- msgraph-sdk 1.2.0 - Microsoft Graph API (Outlook/OneDrive)

**Email:**
- smtplib (stdlib) - SMTP email sending
- jinja2 3.1.3 - Email template rendering

**Utilities:**
- pyyaml 6.0.1 - YAML configuration parsing
- python-dotenv 1.0.0 - Environment variable loading
- httpx 0.26.0 - Async HTTP client
- aiofiles 23.2.1 - Async file operations
- structlog 24.1.0 - Structured logging
- tenacity 8.2.3 - Retry logic and resilience patterns
- alembic 1.13.0 - Database migrations

**Frontend Dependencies:**
- @headlessui/react 1.7.18 - Unstyled accessible components
- @heroicons/react 2.1.1 - SVG icon set
- @tanstack/react-query 5.17.9 - Server state management, data fetching
- @tanstack/react-table 8.11.2 - Headless table component
- axios 1.6.5 - HTTP client for API communication
- chart.js 4.4.1 - Chart rendering
- react-chartjs-2 5.2.0 - React wrapper for Chart.js
- react-router-dom 6.21.2 - Client-side routing
- react-hook-form 7.49.3 - Form state management
- react-hot-toast 2.4.1 - Toast notifications
- react-dropzone 14.2.3 - File upload handling
- zustand 4.4.7 - Lightweight state management
- date-fns 3.2.0 - Date utilities
- clsx 2.1.0 - CSS class composition

## Configuration

**Environment:**
- Environment variables loaded from `.env` file via pydantic-settings
- Separate configuration files for different deployment targets:
  - `.env.example` - Template with required variables
  - `.env.render` - Render.com deployment config
  - Backend: `backend/.env.example`
  - Docker: Variables injected via docker-compose.yml

**Build:**
- `tsconfig.json` - TypeScript compiler configuration for frontend
- `vite.config.ts` - Vite dev server and build configuration
- `alembic.ini` - Database migration configuration
- `docker-compose.yml` - Service orchestration and networking
- Dockerfile variants: `Dockerfile`, `Dockerfile.prod`, `Dockerfile.railway`

## Platform Requirements

**Development:**
- Python 3.11+ with pip
- Node.js 18+ with npm
- Docker and Docker Compose (for containerized services)
- PostgreSQL 16+ (or SQLite for local dev)
- Redis 7+ (for caching and task queue)
- Qdrant vector database (Docker image available)
- Tesseract OCR binary (for document scanning)
- ODA File Converter executable (Windows-specific CAD processing)
- NVIDIA GPU support optional (for Ollama local LLM)

**Production:**
- Cloud platforms supported: Render.com, Railway.app, Fly.io, Vercel
- PostgreSQL database required
- Redis instance for caching/queues
- Qdrant vector database instance
- Google Gemini API key required (GOOGLE_API_KEY env var)
- OpenAI API key optional (OPENAI_API_KEY env var for embeddings)
- SMTP email configuration (Office 365, Gmail, etc.)
- Azure credentials optional (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID for Graph API)

---

*Stack analysis: 2026-02-03*
