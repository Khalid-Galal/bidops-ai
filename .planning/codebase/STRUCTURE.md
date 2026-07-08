# Codebase Structure

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-03

## Directory Layout

```
bidops-ai/
├── backend/                          # Python FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app initialization
│   │   ├── config.py                 # Settings and environment config
│   │   ├── database.py               # SQLAlchemy async session management
│   │   ├── worker.py                 # Background job worker
│   │   ├── api/                      # API layer
│   │   │   ├── deps.py               # Dependency injection (auth, db)
│   │   │   └── v1/                   # API v1 endpoints
│   │   │       ├── router.py         # Main router aggregator
│   │   │       ├── auth.py           # Authentication endpoints
│   │   │       ├── health.py         # Health check endpoint
│   │   │       ├── projects.py       # Project CRUD & management
│   │   │       ├── documents.py      # Document upload & listing
│   │   │       ├── extraction.py     # AI extraction endpoints
│   │   │       ├── packages.py       # BOQ package management
│   │   │       ├── boq.py            # (In packages.py)
│   │   │       ├── suppliers.py      # Supplier management & emails
│   │   │       ├── offers.py         # Offer evaluation & scoring
│   │   │       └── pricing.py        # Pricing analysis & export
│   │   ├── auth/                     # Authentication module
│   │   │   ├── jwt.py                # JWT token encode/decode
│   │   │   ├── password.py           # Password hashing
│   │   │   └── permissions.py        # Permission checking
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── __init__.py           # Model exports
│   │   │   ├── base.py               # Base model, enums, mixins
│   │   │   ├── user.py               # User and Organization models
│   │   │   ├── project.py            # Project model
│   │   │   ├── document.py           # Document model
│   │   │   ├── boq.py                # BOQItem model
│   │   │   ├── package.py            # Package model
│   │   │   ├── offer.py              # Offer and scoring models
│   │   │   ├── supplier.py           # Supplier and contact models
│   │   │   ├── email.py              # Email and communication models
│   │   │   └── audit.py              # Audit trail models
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   │   ├── auth.py               # Auth request/response schemas
│   │   │   ├── common.py             # Common schemas (pagination, responses)
│   │   │   ├── project.py            # Project schemas
│   │   │   ├── document.py           # Document schemas
│   │   │   ├── package.py            # Package schemas
│   │   │   ├── pricing.py            # Pricing schemas
│   │   │   ├── offer.py              # Offer schemas
│   │   │   ├── supplier.py           # Supplier schemas
│   │   │   └── boq.py                # BOQ schemas
│   │   ├── services/                 # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── extraction_service.py # AI extraction logic
│   │   │   ├── document_service.py   # Document processing
│   │   │   ├── boq_service.py        # BOQ management
│   │   │   ├── packaging_service.py  # Package grouping
│   │   │   ├── offer_service.py      # Offer evaluation
│   │   │   ├── pricing_service.py    # Pricing analysis
│   │   │   ├── supplier_service.py   # Supplier operations
│   │   │   ├── email_service.py      # Email handling
│   │   │   ├── export_service.py     # Excel/CSV generation
│   │   │   ├── llm_service.py        # LLM provider abstraction
│   │   │   └── vector_store.py       # Qdrant vector DB client
│   │   ├── parsers/                  # Document format handlers
│   │   │   ├── base.py               # BaseParser interface
│   │   │   ├── pdf_parser.py         # PDF extraction
│   │   │   ├── docx_parser.py        # DOCX extraction
│   │   │   ├── xlsx_parser.py        # Excel extraction
│   │   │   ├── xer_parser.py         # Primavera XER extraction
│   │   │   ├── cad_parser.py         # CAD file extraction
│   │   │   ├── image_parser.py       # Image OCR
│   │   │   ├── email_parser.py       # Email extraction
│   │   │   ├── pptx_parser.py        # PowerPoint extraction
│   │   │   ├── text_parser.py        # Plain text
│   │   │   └── __init__.py           # Parser registry
│   │   ├── prompts/                  # LLM prompt templates
│   │   │   ├── project_summary.py    # Field extraction prompts
│   │   │   ├── checklist.py          # Requirement checklist prompts
│   │   │   ├── classification.py     # Document classification prompts
│   │   │   └── __init__.py
│   │   └── __pycache__/
│   ├── migrations/                   # Alembic database migrations
│   ├── storage/                      # Local file storage
│   │   ├── database/                 # SQLite DB files
│   │   ├── projects/                 # Uploaded project files
│   │   └── temp/                     # Temporary files
│   ├── venv/                         # Python virtual environment
│   ├── requirements.txt               # Python dependencies (if present)
│   └── .env                          # Environment variables (gitignored)
│
├── frontend/                         # React TypeScript frontend
│   ├── src/
│   │   ├── main.tsx                  # React app initialization
│   │   ├── App.tsx                   # Root route configuration
│   │   ├── index.css                 # Global styles (Tailwind)
│   │   ├── vite-env.d.ts             # Vite type definitions
│   │   ├── components/               # Reusable React components
│   │   │   ├── layout/
│   │   │   │   ├── MainLayout.tsx    # Main app wrapper
│   │   │   │   ├── Sidebar.tsx       # Navigation sidebar
│   │   │   │   ├── Header.tsx        # Top header bar
│   │   │   │   └── AuthLayout.tsx    # Auth page wrapper
│   │   │   └── ui/                   # UI primitives
│   │   │       ├── Button.tsx
│   │   │       ├── Card.tsx
│   │   │       ├── Input.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── Badge.tsx
│   │   │       ├── Select.tsx
│   │   │       ├── Spinner.tsx
│   │   │       ├── DataTable.tsx     # Reusable table component
│   │   │       └── index.ts          # Barrel export
│   │   ├── pages/                    # Page-level components
│   │   │   ├── DashboardPage.tsx     # Dashboard with metrics
│   │   │   ├── auth/
│   │   │   │   └── LoginPage.tsx     # Login form
│   │   │   ├── projects/
│   │   │   │   ├── ProjectsPage.tsx  # Project listing
│   │   │   │   └── ProjectDetailPage.tsx # Project detail view
│   │   │   ├── documents/
│   │   │   │   └── DocumentsPage.tsx # Document upload & list
│   │   │   ├── boq/
│   │   │   │   └── BOQPage.tsx       # BOQ item management
│   │   │   ├── packages/
│   │   │   │   ├── PackagesPage.tsx  # Package listing
│   │   │   │   └── PackageDetailPage.tsx # Package detail
│   │   │   ├── suppliers/
│   │   │   │   ├── SuppliersPage.tsx # Supplier listing
│   │   │   │   └── SupplierDetailPage.tsx # Supplier detail
│   │   │   ├── offers/
│   │   │   │   ├── OffersPage.tsx    # Offer listing
│   │   │   │   └── OfferDetailPage.tsx # Offer detail/evaluation
│   │   │   └── pricing/
│   │   │       └── PricingPage.tsx   # Pricing analysis
│   │   ├── hooks/                    # Custom React hooks
│   │   │   ├── useAuth.ts            # Authentication state
│   │   │   ├── useProjects.ts        # Project CRUD hooks
│   │   │   ├── useDocuments.ts       # Document hooks
│   │   │   ├── useDashboard.ts       # Dashboard data hooks
│   │   │   ├── usePackages.ts        # Package hooks
│   │   │   ├── useOffers.ts          # Offer hooks
│   │   │   ├── useSuppliers.ts       # Supplier hooks
│   │   │   └── index.ts              # Barrel export
│   │   ├── services/                 # API service layer
│   │   │   └── api.ts                # Axios instance and helpers
│   │   ├── store/                    # Zustand state stores
│   │   │   ├── authStore.ts          # Auth state (user, token)
│   │   │   └── projectStore.ts       # Project state cache
│   │   ├── types/                    # TypeScript type definitions
│   │   │   └── index.ts              # All types (Project, Document, User, etc.)
│   │   ├── utils/                    # Utility functions
│   │   ├── assets/                   # Static assets (images, icons)
│   │   └── __pycache__/
│   ├── public/                       # Static public assets
│   ├── dist/                         # Built frontend (generated)
│   ├── node_modules/                 # npm dependencies
│   ├── package.json                  # npm configuration
│   ├── package-lock.json
│   ├── tsconfig.json                 # TypeScript config
│   ├── vite.config.ts                # Vite build config
│   ├── tailwind.config.js            # Tailwind CSS config
│   ├── postcss.config.js             # PostCSS config
│   ├── .eslintrc.json                # ESLint config
│   └── index.html                    # HTML entry point
│
├── e2e-tests/                        # Playwright end-to-end tests
│   ├── playwright.config.ts
│   ├── package.json
│   ├── pages/                        # Page object models
│   ├── utils/                        # Test utilities
│   ├── test-files/                   # Sample documents for testing
│   ├── admin-e2e.spec.ts             # Admin flow tests
│   ├── playwright-tests.spec.ts      # Full flow tests
│   ├── test-results/                 # Test execution results
│   └── playwright-report/            # Test report (generated)
│
├── config/                           # Shared configuration
├── docs/                             # Documentation
├── storage/                          # Shared storage directory
├── .git/                             # Git repository
├── .github/                          # GitHub configuration
└── README.md / setup instructions
```

## Directory Purposes

**backend/app:**
- Purpose: Entire FastAPI application code (models, routes, services, logic)
- Contains: Python modules for API, ORM, business logic
- Key files: `main.py` (entry), `config.py` (settings), `database.py` (ORM)

**backend/app/api/v1:**
- Purpose: All REST API endpoint definitions
- Contains: Route handlers organized by domain (projects, documents, offers, etc.)
- Pattern: Each module exposes a router with endpoints for that domain

**backend/app/services:**
- Purpose: Core business logic encapsulation away from HTTP concerns
- Contains: Service classes implementing domain operations
- Pattern: Each service focuses on a single domain (extraction, pricing, documents)

**backend/app/models:**
- Purpose: Database schema definitions via SQLAlchemy ORM
- Contains: Python classes representing tables with relationships
- Pattern: One model per database table, relationships defined via mapped_column and relationship()

**backend/app/parsers:**
- Purpose: Format-specific document content extraction
- Contains: Parser implementations for each supported file type
- Pattern: All inherit from BaseParser, implement async parse() method

**frontend/src/pages:**
- Purpose: Full-page components representing routes
- Contains: Form-heavy, hook-based components for each major feature
- Pattern: One file per route, composes smaller UI components

**frontend/src/components:**
- Purpose: Reusable UI components across pages
- Contains: Layout shells, form inputs, tables, modals
- Pattern: Small, focused components with clear props interfaces

**frontend/src/hooks:**
- Purpose: React Query hooks for data fetching and mutations
- Contains: useProjects, useDocuments, etc. - wrappers around API calls
- Pattern: Each hook uses useQuery or useMutation with queryKey management

**frontend/src/store:**
- Purpose: Client-side state management via Zustand
- Contains: AuthStore (user/token), ProjectStore (cached project list)
- Pattern: Slice-based stores with actions, persisted to localStorage

## Key File Locations

**Entry Points:**
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/main.py`: FastAPI app creation, CORS, exception handlers
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/main.tsx`: React initialization with QueryClient
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/App.tsx`: Route definitions

**Configuration:**
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/config.py`: Environment settings (DB, API keys, paths)
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/vite.config.ts`: Build configuration
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/tsconfig.json`: TypeScript settings

**Core Logic:**
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/database.py`: SQLAlchemy engine and session factory
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/api/deps.py`: Authentication and DB dependency injection
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/services/extraction_service.py`: AI extraction core logic
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/services/api.ts`: Axios instance, upload/download helpers

**Testing:**
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/e2e-tests/playwright.config.ts`: Playwright test configuration
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/e2e-tests/admin-e2e.spec.ts`: Admin feature tests
- `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/e2e-tests/playwright-tests.spec.ts`: Full workflow tests

## Naming Conventions

**Files:**
- Backend: snake_case.py (e.g., `extraction_service.py`, `pdf_parser.py`)
- Frontend: PascalCase.tsx for components (e.g., `MainLayout.tsx`, `ProjectsPage.tsx`), camelCase.ts for utilities
- Models: PascalCase (e.g., `Project`, `Document`, `BOQItem`)
- Schemas: PascalCase with suffix (e.g., `ProjectCreate`, `DocumentResponse`)

**Directories:**
- Backend: lowercase (app, services, models, api)
- Frontend: lowercase plural for collections (components, pages, hooks, services, store)
- By feature: pages organized under feature dir (projects/, suppliers/, offers/)

**Functions/Methods:**
- Backend: snake_case for functions and methods (e.g., `extract_project_summary()`, `parse()`)
- Frontend: camelCase for hooks and functions (e.g., `useProjects()`, `downloadFile()`)

**Classes:**
- PascalCase for both backend (Python) and frontend (TypeScript)
- Service classes: {Domain}Service (e.g., ExtractionService, PricingService)
- Hook naming: use{Feature} (e.g., useProjects, useDocuments)
- Store naming: use{Feature}Store (e.g., useAuthStore, useProjectStore)

## Where to Add New Code

**New Feature (e.g., new domain):**
- Primary code: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/services/{feature}_service.py`
- API endpoint: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/api/v1/{feature}.py`
- Model: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/models/{feature}.py`
- Schema: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/schemas/{feature}.py`
- Frontend page: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/pages/{feature}/{FeaturePage}.tsx`
- Frontend hook: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/hooks/use{Feature}.ts`

**New Component/Module:**
- Reusable component: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/components/{category}/{ComponentName}.tsx`
- Complex component: May have subdirectory under components/ if multiple files needed
- UI primitive: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/components/ui/{ComponentName}.tsx`

**Utilities:**
- Backend utilities: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/utils/{utility_name}.py` (create if doesn't exist)
- Frontend utilities: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/utils/{utilityName}.ts`
- Shared helpers (parsing, validation): Keep in service layer if domain-specific, in utils if cross-cutting

**Types & Schemas:**
- Frontend types: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/types/index.ts` (central location)
- Backend schemas: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/schemas/{feature}.py`
- Shared enums: In `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/models/base.py` (ProjectStatus, DocumentCategory, UserRole)

## Special Directories

**backend/migrations:**
- Purpose: Alembic database migration scripts
- Generated: Yes, by Alembic
- Committed: Yes, should be committed to track schema changes
- Usage: Run migrations with `alembic upgrade head`

**frontend/dist:**
- Purpose: Built frontend static files ready for deployment
- Generated: Yes, by `npm run build`
- Committed: No, should be gitignored (generated artifact)
- Recreated by: `npm run build` which runs `tsc && vite build`

**backend/storage:**
- Purpose: Local file storage for uploads and database
- Generated: Yes, populated at runtime
- Committed: No, gitignored
- Contains: SQLite DB file, project uploads, temporary files

**frontend/node_modules:**
- Purpose: npm installed dependencies
- Generated: Yes, by `npm install`
- Committed: No, gitignored
- Recreated by: `npm install` from package-lock.json

**e2e-tests/test-results:**
- Purpose: Playwright test execution results and artifacts
- Generated: Yes, by test runs
- Committed: No, gitignored
- Contains: Screenshots, videos, JSON results

**frontend/public:**
- Purpose: Static assets served at root
- Generated: No, manually maintained
- Committed: Yes
- Usage: favicon.ico, robots.txt, etc.

---

*Structure analysis: 2026-02-03*
