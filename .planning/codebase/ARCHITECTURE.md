# Architecture

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-03

## Pattern Overview

**Overall:** Layered three-tier architecture with separation between frontend (React/SPA), backend API (FastAPI), and data services (parsers, LLM, vector store).

**Key Characteristics:**
- Async-first backend using FastAPI and SQLAlchemy async ORM
- Modular service layer for domain logic (extraction, pricing, packaging, etc.)
- Client-driven state management on frontend using Zustand + React Query
- Event-driven document processing pipeline with LLM integration
- Plugin-based document parser architecture supporting multiple file formats

## Layers

**Presentation Layer (Frontend):**
- Purpose: Single Page Application providing UI for tender/bidding workflows
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src`
- Contains: React components, pages, hooks, stores, services
- Depends on: Backend API (`/api/v1`), Zustand for state, React Query for server state
- Used by: End users accessing tender management, document upload, offer evaluation

**API Layer (FastAPI):**
- Purpose: RESTful HTTP endpoints for all business operations
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/api/v1`
- Contains: Route handlers (projects, documents, extraction, packages, suppliers, offers, pricing, auth)
- Depends on: Service layer, database layer, authentication/authorization
- Used by: Frontend SPA, potentially third-party integrations

**Service Layer:**
- Purpose: Core business logic encapsulation
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/services`
- Contains: ExtractionService, DocumentService, BOQService, PricingService, OfferService, etc.
- Depends on: Database layer, external services (LLM, vector store), parser layer
- Used by: API endpoints to execute business operations

**Data Access Layer:**
- Purpose: Database interactions and ORM management
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/database.py`
- Contains: Async SQLAlchemy session factory, database initialization
- Depends on: SQLAlchemy, SQLite/PostgreSQL drivers
- Used by: All service and API layers for data persistence

**Domain Models:**
- Purpose: Database schema definitions and data validation
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/models`
- Contains: SQLAlchemy ORM models (Project, Document, User, Organization, BOQItem, Package, Offer, Supplier)
- Depends on: SQLAlchemy, database layer
- Used by: Service and data access layers

**Parser Layer:**
- Purpose: Document format-specific content extraction
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/parsers`
- Contains: BaseParser interface, PDF parser, DOCX parser, Excel parser, CAD parser, image parser, text parser, email parser
- Depends on: External libraries (pypdf, python-docx, openpyxl, etc.)
- Used by: DocumentService for processing uploaded files

**Authentication & Authorization:**
- Purpose: User identity and permission validation
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/auth`
- Contains: JWT token handling, password hashing, permission checking
- Depends on: JWT library, hashing functions
- Used by: API dependency injection system to protect endpoints

## Data Flow

**Document Upload & Processing Flow:**

1. User uploads document via frontend DocumentsPage
2. Frontend calls `POST /api/v1/documents/upload` with file
3. DocumentService receives file, selects appropriate parser based on extension
4. Parser extracts structured content (text, tables, pages, images)
5. Parsed content stored in Project.documents with extracted_text field
6. Document indexed in vector store (Qdrant) for semantic search
7. Frontend receives upload confirmation, displays document metadata

**Project Summary Extraction Flow:**

1. User triggers extraction via frontend ProjectDetailPage or API
2. ExtractionService retrieves all indexed documents for project
3. LLMService queries vector store for relevant document chunks per field
4. Prompt builder creates extraction prompt with field definitions and examples
5. LLM (Google Gemini) processes chunks and extracts values with evidence citations
6. Results stored in Project.summary (JSON with field values, confidence scores, evidence)
7. ChecklistService generates requirements checklist from tender documents
8. Frontend displays extracted summary with confidence indicators

**Offer Evaluation Flow:**

1. User inputs supplier pricing via OffersPage form
2. OfferService calculates evaluation scores based on project checklist and pricing weights
3. PricingService generates comparative analysis and spreadsheets
4. BOQService reconciles supplier offers against project BOQ items
5. Results stored in Offer records with detailed scoring breakdown
6. Frontend displays offer rankings, comparison matrices, export options

**Package/BOQ Management:**

1. User creates or imports BOQ items via BOQPage
2. PackagingService groups BOQ items into packages based on configuration
3. Each package linked to project with cost and schedule impact
4. OfferService uses package structure for supplier evaluation
5. Frontend allows drag-and-drop reordering and bulk operations

## Key Abstractions

**BaseParser Interface:**
- Purpose: Abstraction for document format handling
- Examples: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/parsers/pdf_parser.py`, `docx_parser.py`, `xlsx_parser.py`
- Pattern: Strategy pattern - each parser implements parse(file_path) -> ParsedContent

**ParsedContent Dataclass:**
- Purpose: Normalized document extraction result across all parser types
- Pattern: Contains text, tables, pages, images, metadata, warnings, and processing metrics
- Allows downstream services to operate uniformly regardless of source format

**LLMService:**
- Purpose: Abstraction over LLM provider selection and execution
- Pattern: Supports multiple providers (Google Gemini, OpenAI with fallback)
- Used by: ExtractionService for all AI operations

**VectorStoreService:**
- Purpose: Semantic search and document indexing
- Pattern: Currently Qdrant-based, provides embed_and_store(), search(), delete() operations
- Used by: ExtractionService, document service for context retrieval

**Service Layer Cohesion:**
- ExtractionService: Project summary + checklist generation
- DocumentService: File upload, parsing, indexing, metadata
- BOQService: Bill of Quantities management and reconciliation
- PricingService: Cost analysis, comparative spreadsheets, dashboards
- OfferService: Supplier offer evaluation, scoring, rankings
- PackagingService: BOQ item grouping and package creation
- SupplierService: Supplier management, contact tracking, communication

## Entry Points

**Backend Entry Point:**
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/main.py`
- Triggers: FastAPI application startup (lifespan context manager)
- Responsibilities: CORS configuration, exception handling, static file serving, router registration

**Frontend Entry Point:**
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/main.tsx`
- Triggers: React application initialization
- Responsibilities: QueryClient setup, routing configuration, provider wrapping (React Query, Router)

**API Router:**
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/api/v1/router.py`
- Triggers: FastAPI router inclusion in main.py
- Responsibilities: Routes all v1 requests to appropriate sub-routers (projects, documents, extraction, etc.)

**Authentication Dependency:**
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/api/deps.py`
- Triggers: API route protection via Depends()
- Responsibilities: JWT token validation, user lookup, permission checking

**App Component:**
- Location: `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/App.tsx`
- Triggers: After React initialization
- Responsibilities: Route definitions, protected route wrapping, layout nesting

## Error Handling

**Strategy:** Centralized exception handlers in FastAPI with environment-aware responses

**Patterns:**
- Validation errors caught by FastAPI middleware, returned with field-level detail
- Business logic errors wrapped in HTTPException with appropriate status codes
- Uncaught exceptions caught by general_exception_handler - detailed in debug, generic in production
- Frontend handles API errors with toast notifications and error boundary displays
- Service layer raises Python exceptions (ValueError, custom exceptions) propagated to API layer

## Cross-Cutting Concerns

**Logging:**
- Backend: Print statements in main.py for startup/shutdown; settings control debug output
- Frontend: Console logging via React DevTools and query devtools
- No centralized logging service implemented

**Validation:**
- Backend: Pydantic schemas in `D:/Work/intercom/intercom_projects/Hassan/bidops-ai/backend/app/schemas` for request/response validation
- Frontend: React Hook Form for client-side form validation
- Database: SQLAlchemy constraints and nullable fields enforce data integrity

**Authentication:**
- JWT tokens via HTTPBearer security scheme
- Token structure includes user_id (sub), token type, expiration
- Refresh tokens supported for extended sessions
- Frontend stores auth state in Zustand with localStorage persistence

**Authorization:**
- Role-based access control (ADMIN, TENDER_MANAGER, ANALYST, VIEWER)
- Permission checking in deps.py via require_permission() and require_role() decorators
- Organization-scoped data queries ensure multi-tenancy

---

*Architecture analysis: 2026-02-03*
