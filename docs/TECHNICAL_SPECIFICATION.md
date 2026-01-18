# BidOps AI - Technical Specification Document

**Version:** 1.0
**Date:** 2026-01-04
**Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Data Models](#4-data-models)
5. [API Specification](#5-api-specification)
6. [Core Services](#6-core-services)
7. [AI/LLM Integration](#7-aillm-integration)
8. [Document Processing Pipeline](#8-document-processing-pipeline)
9. [CAD/BIM File Handling](#9-cadbim-file-handling)
10. [Security & Authentication](#10-security--authentication)
11. [Deployment Architecture](#11-deployment-architecture)
12. [File Structure](#12-file-structure)
13. [Implementation Phases](#13-implementation-phases)

---

## 1. Executive Summary

### 1.1 Purpose

BidOps AI is a production-grade desktop+web hybrid application that automates tender/bidding operations end-to-end for contracting companies. It processes heterogeneous project documents, extracts structured data, manages supplier communications, evaluates offers, and produces client-ready pricing deliverables.

### 1.2 Key Capabilities

| Capability | Description |
|------------|-------------|
| Document Ingestion | Parse PDF, DOCX, XLSX, PPTX, MSG/EML, TXT, images, ZIP, DWG, DXF, IFC, XER/XML |
| Multilingual Support | Arabic, English, and auto-detected languages |
| Project Summary Extraction | Structured metadata with confidence scores and citations |
| Requirements Checklist | Auto-generated compliance checklist from tender documents |
| BOQ Packaging | Intelligent grouping with document-to-item mapping |
| Supplier Management | Email automation, offer tracking, clarification workflows |
| Offer Evaluation | Technical & commercial comparison with weighted scoring |
| Price Population | Client template filling with gap analysis |
| Historical Learning | Benchmark pricing from historical database |

### 1.3 Deployment Model

- **Primary:** Local network server (Windows Server / Linux)
- **Access:** Web interface for multiple concurrent users
- **Database:** Shared PostgreSQL + Qdrant vector store
- **Offline:** Core functions work without internet (local LLM fallback)

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   CLIENTS                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Desktop    │  │   Browser    │  │   Mobile     │  │   API        │         │
│  │  (Electron)  │  │   (React)    │  │   (Future)   │  │  Consumers   │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┘
          │                 │                 │                 │
          └────────────────┬┴─────────────────┴─────────────────┘
                           │ HTTPS / WSS
          ┌────────────────┴────────────────┐
          │         NGINX (Reverse Proxy)   │
          │         + SSL Termination       │
          └────────────────┬────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────────────────────┐
│                              APPLICATION LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         FastAPI Backend                                  │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │    │
│  │  │   REST API  │  │  WebSocket  │  │  GraphQL    │  │  Background │     │    │
│  │  │  Endpoints  │  │   Server    │  │  (Optional) │  │   Workers   │     │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│  ┌───────────────────────────────────┴───────────────────────────────────────┐  │
│  │                           CORE SERVICES                                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │  Document   │  │  AI/LLM     │  │  Packaging  │  │  Supplier   │       │  │
│  │  │  Service    │  │  Service    │  │  Service    │  │  Service    │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ Evaluation  │  │  Pricing    │  │  Email      │  │  Reporting  │       │  │
│  │  │  Service    │  │  Service    │  │  Service    │  │  Service    │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                           │
│  ┌───────────────────────────────────┴───────────────────────────────────────┐  │
│  │                           AI AGENTS (LangGraph)                            │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │  │
│  │  │ Archivist │ │    QS     │ │Procurement│ │ Evaluator │ │ Estimator │    │  │
│  │  │   Agent   │ │   Agent   │ │   Agent   │ │   Agent   │ │   Agent   │    │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────────────────┐
│                                DATA LAYER                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                   │
│  │   PostgreSQL    │  │     Qdrant      │  │      Redis      │                   │
│  │  (Structured)   │  │    (Vectors)    │  │  (Cache/Queue)  │                   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                   │
│  ┌─────────────────────────────────────────────────────────────┐                 │
│  │                    File Storage (NFS/SMB)                   │                 │
│  │  ├── /projects/{id}/documents/                              │                 │
│  │  ├── /projects/{id}/packages/                               │                 │
│  │  ├── /projects/{id}/offers/                                 │                 │
│  │  └── /database/historical/                                  │                 │
│  └─────────────────────────────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────────────────┐
│                             EXTERNAL SERVICES                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   OpenAI    │  │   Ollama    │  │  Microsoft  │  │   OneDrive  │              │
│  │   API       │  │   (Local)   │  │   Graph     │  │  SharePoint │              │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘              │
│  ┌─────────────┐  ┌─────────────┐                                                │
│  │   Google    │  │    SMTP     │                                                │
│  │   Drive     │  │   Server    │                                                │
│  └─────────────┘  └─────────────┘                                                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Interaction Flow

```
User Request → API Gateway → Authentication → Rate Limiter → Router
                                                               │
                    ┌──────────────────────────────────────────┴──────────┐
                    │                                                      │
            Synchronous Request                               Async Task Request
                    │                                                      │
                    ▼                                                      ▼
            Service Layer ────────────────────────────────────────→ Task Queue (ARQ)
                    │                                                      │
                    ▼                                                      ▼
            Data Access Layer                                       Background Worker
                    │                                                      │
                    ▼                                                      ▼
            Database/Cache                                          AI Agent Pipeline
                    │                                                      │
                    ▼                                                      │
            Response ←─────────────────────────────────────────────────────┘
                                     (via WebSocket for progress)
```

---

## 3. Technology Stack

### 3.1 Backend Technologies

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| **Runtime** | Python | 3.11+ | Type hints, async support, ML ecosystem |
| **Framework** | FastAPI | 0.109+ | Async, OpenAPI docs, validation |
| **Task Queue** | ARQ | 0.25+ | Async Redis-based, lightweight |
| **ORM** | SQLAlchemy | 2.0+ | Async support, mature, migrations |
| **Migrations** | Alembic | 1.13+ | Database schema versioning |
| **Validation** | Pydantic | 2.5+ | Settings, request/response models |

### 3.2 AI/ML Technologies

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| **LLM Orchestration** | LangGraph | 0.1+ | State machines, better than CrewAI for production |
| **LLM Framework** | LangChain | 0.2+ | LCEL, tool calling, streaming |
| **Cloud LLM** | OpenAI GPT-4o | Latest | Best extraction quality |
| **Local LLM** | Ollama + Llama 3.1 | 70B/8B | Offline fallback, privacy |
| **Embeddings** | OpenAI text-embedding-3-small | - | Multilingual, cost-effective |
| **Local Embeddings** | sentence-transformers | - | Offline fallback |
| **Vector Store** | Qdrant | 1.7+ | Production-ready, filtering, hybrid search |

### 3.3 Database Technologies

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| **Primary DB** | PostgreSQL | 16+ | JSONB, full-text search, reliability |
| **Vector DB** | Qdrant | 1.7+ | Hybrid search, filtering, scalability |
| **Cache** | Redis | 7+ | Session, queue backend, caching |
| **Search** | PostgreSQL FTS | - | Arabic/English full-text search |

### 3.4 Document Processing

| File Type | Library | Notes |
|-----------|---------|-------|
| **PDF** | PyMuPDF (fitz) | Fast, preserves layout |
| **PDF OCR** | pytesseract + pdf2image | For scanned documents |
| **DOCX** | python-docx | Standard library |
| **XLSX** | openpyxl | Read/write with styles |
| **PPTX** | python-pptx | Extract text/images |
| **MSG** | extract-msg | Outlook messages |
| **EML** | email (stdlib) | Standard email parsing |
| **Images** | Pillow + pytesseract | OCR for images |
| **DXF** | ezdxf | AutoCAD exchange format |
| **DWG** | ODA File Converter (external) | Convert to DXF first |
| **IFC** | ifcopenshell | BIM file parsing |
| **XER** | xerparser + custom | Primavera exports |
| **ZIP** | zipfile (stdlib) | Archive extraction |

### 3.5 Frontend Technologies

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| **Desktop Shell** | Electron | 28+ | Cross-platform desktop |
| **Build Tool** | Vite | 5+ | Fast HMR, ESM native |
| **UI Framework** | React | 18+ | Component ecosystem |
| **Language** | TypeScript | 5.3+ | Type safety |
| **UI Components** | shadcn/ui | Latest | Accessible, customizable |
| **State** | Zustand | 4+ | Simple, minimal boilerplate |
| **Data Fetching** | TanStack Query | 5+ | Caching, mutations |
| **Forms** | React Hook Form + Zod | - | Validation, performance |
| **Tables** | TanStack Table | 8+ | Virtual scrolling, sorting |
| **Charts** | Recharts | 2+ | Responsive charts |

### 3.6 DevOps & Infrastructure

| Component | Technology | Justification |
|-----------|------------|---------------|
| **Containerization** | Docker + Compose | Local development, deployment |
| **Reverse Proxy** | Nginx | SSL, load balancing |
| **Process Manager** | Supervisor / systemd | Service management |
| **Monitoring** | Prometheus + Grafana | Metrics, alerting |
| **Logging** | Structlog + Loki | Structured logging |

---

## 4. Data Models

### 4.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │       │   Organization  │       │      Role       │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id              │───────│ id              │───────│ id              │
│ email           │       │ name            │       │ name            │
│ password_hash   │       │ settings        │       │ permissions     │
│ full_name       │       │ created_at      │       └─────────────────┘
│ role_id         │       └─────────────────┘
│ org_id          │
└─────────────────┘
         │
         │ creates/manages
         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     Project     │       │    Document     │       │   Embedding     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id              │──────▶│ id              │──────▶│ id              │
│ name            │       │ project_id      │       │ document_id     │
│ status          │       │ filename        │       │ chunk_text      │
│ folder_path     │       │ file_path       │       │ chunk_index     │
│ summary_json    │       │ file_type       │       │ vector_id       │
│ config_json     │       │ content_hash    │       │ metadata        │
│ created_by      │       │ extracted_text  │       └─────────────────┘
│ created_at      │       │ metadata_json   │
│ updated_at      │       │ page_count      │
└─────────────────┘       │ status          │
         │                │ created_at      │
         │                └─────────────────┘
         │
         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     BOQItem     │       │     Package     │       │ PackageDocument │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id              │──────▶│ id              │◀──────│ id              │
│ project_id      │       │ project_id      │       │ package_id      │
│ package_id      │       │ name            │       │ document_id     │
│ line_number     │       │ trade_category  │       │ relevance_score │
│ description     │       │ status          │       │ excerpt         │
│ unit            │       │ created_at      │       └─────────────────┘
│ quantity        │       └─────────────────┘
│ client_ref      │                │
│ mapped_offer_id │                │
│ confidence      │                ▼
└─────────────────┘       ┌─────────────────┐
                          │    Supplier     │
                          ├─────────────────┤
┌─────────────────┐       │ id              │
│  SupplierOffer  │──────▶│ name            │
├─────────────────┤       │ email           │
│ id              │       │ trade_category  │
│ package_id      │       │ region          │
│ supplier_id     │       │ rating          │
│ status          │       │ notes           │
│ file_path       │       │ max_attachment  │
│ total_price     │       └─────────────────┘
│ currency        │
│ validity_date   │       ┌─────────────────┐
│ payment_terms   │       │   EmailLog      │
│ exclusions      │       ├─────────────────┤
│ deviations      │◀──────│ id              │
│ tech_score      │       │ package_id      │
│ comm_score      │       │ supplier_id     │
│ compliance_json │       │ email_type      │
│ created_at      │       │ subject         │
└─────────────────┘       │ body            │
                          │ attachments     │
                          │ status          │
                          │ message_id      │
                          │ sent_at         │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│  AuditLog       │       │ Configuration   │
├─────────────────┤       ├─────────────────┤
│ id              │       │ id              │
│ user_id         │       │ project_id      │
│ action          │       │ key             │
│ entity_type     │       │ value           │
│ entity_id       │       │ type            │
│ old_value       │       └─────────────────┘
│ new_value       │
│ timestamp       │
└─────────────────┘
```

### 4.2 SQLAlchemy Models

```python
# models/base.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

class Base(DeclarativeBase):
    pass

class ProjectStatus(enum.Enum):
    DRAFT = "draft"
    INGESTING = "ingesting"
    READY = "ready"
    PACKAGING = "packaging"
    BIDDING = "bidding"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class DocumentStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"

class PackageStatus(enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    OFFERS_RECEIVED = "offers_received"
    EVALUATED = "evaluated"
    AWARDED = "awarded"

class OfferStatus(enum.Enum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    CLARIFICATION_SENT = "clarification_sent"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    SELECTED = "selected"
    REJECTED = "rejected"
```

```python
# models/project.py
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    folder_path: Mapped[str] = mapped_column(String(1024))
    cloud_link: Mapped[Optional[str]] = mapped_column(String(1024))
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)

    # Extracted summary with evidence
    summary: Mapped[Optional[dict]] = mapped_column(JSON)
    checklist: Mapped[Optional[dict]] = mapped_column(JSON)

    # Configuration
    config: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    documents: Mapped[list["Document"]] = relationship(back_populates="project")
    packages: Mapped[list["Package"]] = relationship(back_populates="project")
    boq_items: Mapped[list["BOQItem"]] = relationship(back_populates="project")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=func.now())
```

```python
# models/document.py
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))

    filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(50))  # pdf, docx, xlsx, dwg, etc.
    file_size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256

    # Extracted content
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON)  # title, author, dates, etc.

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Classification
    document_category: Mapped[Optional[str]] = mapped_column(String(100))  # ITT, Specs, BOQ, Drawing, Contract
    language: Mapped[Optional[str]] = mapped_column(String(10))  # en, ar, etc.

    # Versioning
    is_superseded: Mapped[bool] = mapped_column(default=False)
    superseded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"))

    project: Mapped["Project"] = relationship(back_populates="documents")
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="document")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

```python
# models/boq.py
class BOQItem(Base):
    __tablename__ = "boq_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    package_id: Mapped[Optional[int]] = mapped_column(ForeignKey("packages.id"))

    # BOQ Data
    line_number: Mapped[str] = mapped_column(String(50))
    section: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[float] = mapped_column(Float)

    # Client reference
    client_ref: Mapped[Optional[str]] = mapped_column(String(100))

    # Classification (AI-generated)
    trade_category: Mapped[Optional[str]] = mapped_column(String(100))
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Pricing (after offer selection)
    selected_offer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier_offers.id"))
    unit_rate: Mapped[Optional[float]] = mapped_column(Float)
    total_price: Mapped[Optional[float]] = mapped_column(Float)

    # Mapping confidence
    mapping_confidence: Mapped[Optional[float]] = mapped_column(Float)
    requires_review: Mapped[bool] = mapped_column(default=False)

    project: Mapped["Project"] = relationship(back_populates="boq_items")
    package: Mapped[Optional["Package"]] = relationship(back_populates="items")
```

```python
# models/package.py
class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))

    name: Mapped[str] = mapped_column(String(255))
    package_code: Mapped[str] = mapped_column(String(50))  # e.g., PKG-001
    trade_category: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[PackageStatus] = mapped_column(Enum(PackageStatus), default=PackageStatus.DRAFT)

    # Linked documents (specs, drawings relevant to this package)
    linked_document_ids: Mapped[Optional[list]] = mapped_column(JSON)

    # Submission deadline for suppliers
    submission_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)

    project: Mapped["Project"] = relationship(back_populates="packages")
    items: Mapped[list["BOQItem"]] = relationship(back_populates="package")
    offers: Mapped[list["SupplierOffer"]] = relationship(back_populates="package")
    email_logs: Mapped[list["EmailLog"]] = relationship(back_populates="package")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

```python
# models/supplier.py
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))

    name: Mapped[str] = mapped_column(String(255))
    emails: Mapped[list] = mapped_column(JSON)  # List of email addresses
    phone: Mapped[Optional[str]] = mapped_column(String(50))

    trade_categories: Mapped[list] = mapped_column(JSON)  # List of trades
    region: Mapped[Optional[str]] = mapped_column(String(100))

    rating: Mapped[Optional[float]] = mapped_column(Float)  # 1-5
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Preferences
    preferred_format: Mapped[Optional[str]] = mapped_column(String(50))  # pdf, excel
    max_attachment_size_mb: Mapped[Optional[int]] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(default=True)

    offers: Mapped[list["SupplierOffer"]] = relationship(back_populates="supplier")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    status: Mapped[OfferStatus] = mapped_column(Enum(OfferStatus), default=OfferStatus.RECEIVED)

    # File references
    file_paths: Mapped[list] = mapped_column(JSON)  # List of uploaded files

    # Extracted commercial data
    total_price: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    validity_days: Mapped[Optional[int]] = mapped_column(Integer)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    delivery_time: Mapped[Optional[str]] = mapped_column(String(100))

    # Compliance analysis
    exclusions: Mapped[Optional[list]] = mapped_column(JSON)
    deviations: Mapped[Optional[list]] = mapped_column(JSON)
    missing_items: Mapped[Optional[list]] = mapped_column(JSON)

    # Scoring
    technical_score: Mapped[Optional[float]] = mapped_column(Float)
    commercial_score: Mapped[Optional[float]] = mapped_column(Float)
    overall_score: Mapped[Optional[float]] = mapped_column(Float)

    # Full compliance analysis JSON
    compliance_analysis: Mapped[Optional[dict]] = mapped_column(JSON)

    # Line item pricing
    line_items: Mapped[Optional[list]] = mapped_column(JSON)  # Parsed price breakdown

    package: Mapped["Package"] = relationship(back_populates="offers")
    supplier: Mapped["Supplier"] = relationship(back_populates="offers")

    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
```

---

## 5. API Specification

### 5.1 API Overview

Base URL: `http://localhost:8000/api/v1`

Authentication: JWT Bearer Token

### 5.2 Endpoints

#### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/projects` | Create new project |
| `GET` | `/projects` | List all projects |
| `GET` | `/projects/{id}` | Get project details |
| `PATCH` | `/projects/{id}` | Update project |
| `DELETE` | `/projects/{id}` | Delete project |
| `POST` | `/projects/{id}/ingest` | Start document ingestion |
| `GET` | `/projects/{id}/summary` | Get extracted summary |
| `GET` | `/projects/{id}/checklist` | Get requirements checklist |
| `POST` | `/projects/{id}/generate-packages` | Generate packages from BOQ |

#### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/projects/{id}/documents` | List project documents |
| `POST` | `/projects/{id}/documents/upload` | Upload document |
| `GET` | `/documents/{id}` | Get document details |
| `GET` | `/documents/{id}/content` | Get extracted content |
| `POST` | `/documents/search` | Semantic search across documents |

#### Packages

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/projects/{id}/packages` | List packages |
| `POST` | `/projects/{id}/packages` | Create package |
| `GET` | `/packages/{id}` | Get package details |
| `PATCH` | `/packages/{id}` | Update package |
| `POST` | `/packages/{id}/send-rfq` | Send RFQ to suppliers |
| `GET` | `/packages/{id}/offers` | List received offers |

#### Suppliers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/suppliers` | List suppliers |
| `POST` | `/suppliers` | Create supplier |
| `POST` | `/suppliers/import` | Import from Excel |
| `GET` | `/suppliers/{id}` | Get supplier details |
| `PATCH` | `/suppliers/{id}` | Update supplier |

#### Offers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/packages/{id}/offers` | Upload offer |
| `GET` | `/offers/{id}` | Get offer details |
| `POST` | `/offers/{id}/evaluate` | Evaluate offer |
| `POST` | `/offers/{id}/clarification` | Send clarification request |
| `GET` | `/packages/{id}/comparison` | Get comparison matrix |

#### Pricing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/projects/{id}/populate-boq` | Populate client BOQ |
| `POST` | `/projects/{id}/populate-indirects` | Populate indirects |
| `GET` | `/projects/{id}/pricing-gaps` | Get pricing gaps report |
| `GET` | `/projects/{id}/export` | Export final deliverables |

### 5.3 WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `ingestion.progress` | Server→Client | Document processing progress |
| `ingestion.complete` | Server→Client | Ingestion finished |
| `extraction.field` | Server→Client | Summary field extracted |
| `package.created` | Server→Client | Package generated |
| `offer.received` | Server→Client | New offer uploaded |
| `evaluation.complete` | Server→Client | Offer evaluation done |

### 5.4 Request/Response Examples

#### Create Project

```http
POST /api/v1/projects
Content-Type: application/json

{
  "name": "Marina Tower - MEP Package",
  "folder_path": "D:\\Projects\\Marina_Tower",
  "config": {
    "scoring_weights": {
      "technical": 0.6,
      "commercial": 0.4
    },
    "currency": "AED",
    "language": "en"
  }
}
```

Response:

```json
{
  "id": 1,
  "name": "Marina Tower - MEP Package",
  "status": "draft",
  "folder_path": "D:\\Projects\\Marina_Tower",
  "created_at": "2026-01-04T10:30:00Z"
}
```

#### Get Project Summary

```http
GET /api/v1/projects/1/summary
```

Response:

```json
{
  "project_name": {
    "value": "Marina Tower Development - Phase 2",
    "confidence": 0.95,
    "evidence": [
      {
        "document": "ITT_Document.pdf",
        "page": 1,
        "section": "Cover Page",
        "snippet": "Invitation to Tender: Marina Tower Development - Phase 2"
      }
    ]
  },
  "project_owner": {
    "value": "Marina Development LLC",
    "confidence": 0.92,
    "evidence": [...]
  },
  "submission_deadline": {
    "value": "2026-02-15T14:00:00",
    "confidence": 0.98,
    "evidence": [...]
  },
  "contract_type": {
    "value": "Lump Sum",
    "confidence": 0.88,
    "evidence": [...]
  }
}
```

---

## 6. Core Services

### 6.1 DocumentService

**Purpose:** Handle document parsing, text extraction, and indexing.

```python
# services/document_service.py

class DocumentService:
    """
    Responsible for:
    - File type detection
    - Text extraction (with OCR fallback)
    - Metadata extraction
    - Vector embedding generation
    - Incremental indexing
    """

    async def ingest_folder(self, project_id: int, folder_path: str) -> IngestResult:
        """Walk folder, parse documents, generate embeddings."""
        pass

    async def parse_document(self, file_path: str) -> ParsedDocument:
        """Extract text and metadata from a single document."""
        pass

    async def search(self, query: str, project_id: int, filters: dict) -> list[SearchResult]:
        """Semantic + keyword search across documents."""
        pass

    async def get_relevant_excerpts(self, query: str, document_ids: list[int]) -> list[Excerpt]:
        """Find relevant passages for a specific query."""
        pass
```

### 6.2 AIService

**Purpose:** LLM orchestration for extraction, analysis, and generation.

```python
# services/ai_service.py

class AIService:
    """
    Responsible for:
    - Project summary extraction with citations
    - Requirements checklist generation
    - BOQ item classification
    - Offer compliance analysis
    - Clarification email drafting
    """

    def __init__(self, config: AIConfig):
        self.cloud_llm = ChatOpenAI(model="gpt-4o")
        self.local_llm = OllamaLLM(model="llama3.1:70b")

    async def extract_project_summary(self, project_id: int) -> ProjectSummary:
        """Extract structured summary with evidence citations."""
        pass

    async def generate_checklist(self, project_id: int) -> list[ChecklistItem]:
        """Generate requirements checklist from tender documents."""
        pass

    async def classify_boq_items(self, items: list[BOQItem]) -> list[ClassifiedItem]:
        """Classify BOQ items into trade categories."""
        pass

    async def analyze_offer(self, offer_id: int, requirements: dict) -> OfferAnalysis:
        """Compare offer against requirements, identify gaps."""
        pass

    async def draft_clarification(self, offer_id: int, gaps: list[Gap]) -> str:
        """Generate clarification email for supplier."""
        pass
```

### 6.3 PackagingService

**Purpose:** Group BOQ items into procurement packages.

```python
# services/packaging_service.py

class PackagingService:
    """
    Responsible for:
    - BOQ parsing and standardization
    - Intelligent item grouping by trade
    - Document-to-package linking
    - Package folder creation
    - Package brief generation
    """

    async def parse_boq(self, file_path: str) -> list[BOQItem]:
        """Parse BOQ Excel and extract items."""
        pass

    async def generate_packages(self, project_id: int, config: PackagingConfig) -> list[Package]:
        """Group BOQ items into packages with linked documents."""
        pass

    async def link_documents(self, package_id: int) -> list[LinkedDocument]:
        """Find relevant specs/drawings for package items."""
        pass

    async def create_package_folder(self, package: Package) -> str:
        """Create folder structure with BOQ subset and briefs."""
        pass

    async def generate_package_brief(self, package: Package) -> bytes:
        """Generate PDF brief for package."""
        pass
```

### 6.4 SupplierService

**Purpose:** Manage supplier database and communications.

```python
# services/supplier_service.py

class SupplierService:
    """
    Responsible for:
    - Supplier CRUD operations
    - Excel import/export
    - Supplier-package matching
    """

    async def import_from_excel(self, file_path: str) -> ImportResult:
        """Import suppliers from Excel."""
        pass

    async def match_suppliers_to_package(self, package: Package) -> list[Supplier]:
        """Find suitable suppliers for a package based on trade."""
        pass

    async def get_supplier_performance(self, supplier_id: int) -> SupplierStats:
        """Get historical performance metrics."""
        pass
```

### 6.5 EmailService

**Purpose:** Handle email sending via Graph API or SMTP.

```python
# services/email_service.py

class EmailService:
    """
    Responsible for:
    - Microsoft Graph API integration
    - SMTP fallback
    - Email template rendering
    - Attachment handling
    - Email logging
    """

    async def send_rfq(self, package: Package, suppliers: list[Supplier],
                       draft_only: bool = False) -> list[EmailLog]:
        """Send RFQ to suppliers."""
        pass

    async def send_clarification(self, offer: SupplierOffer, queries: list[str],
                                  draft_only: bool = False) -> EmailLog:
        """Send clarification request."""
        pass

    async def get_email_template(self, template_name: str, context: dict) -> str:
        """Render email template with context."""
        pass
```

### 6.6 EvaluationService

**Purpose:** Compare and score supplier offers.

```python
# services/evaluation_service.py

class EvaluationService:
    """
    Responsible for:
    - Offer parsing (PDF/Excel/Word)
    - Requirement compliance checking
    - Technical scoring
    - Commercial comparison
    - Weighted ranking
    - Comparison matrix generation
    """

    async def parse_offer(self, offer_id: int) -> ParsedOffer:
        """Extract pricing and terms from offer documents."""
        pass

    async def evaluate_compliance(self, offer: SupplierOffer,
                                   requirements: list[Requirement]) -> ComplianceResult:
        """Check offer against requirements."""
        pass

    async def score_offer(self, offer: SupplierOffer, weights: ScoringWeights) -> OfferScore:
        """Calculate technical and commercial scores."""
        pass

    async def generate_comparison_matrix(self, package_id: int) -> bytes:
        """Generate Excel comparison matrix."""
        pass

    async def recommend_shortlist(self, package_id: int) -> list[Recommendation]:
        """Recommend best offers with rationale."""
        pass
```

### 6.7 PricingService

**Purpose:** Populate client BOQ and indirects templates.

```python
# services/pricing_service.py

class PricingService:
    """
    Responsible for:
    - Item mapping (offer → client BOQ)
    - Template population (preserving formulas)
    - Gap analysis
    - Historical benchmarking
    - Indirects calculation
    """

    async def map_items(self, offer: SupplierOffer, boq_items: list[BOQItem]) -> list[ItemMapping]:
        """Map offer line items to client BOQ items."""
        pass

    async def populate_client_boq(self, project_id: int, template_path: str,
                                   mappings: list[ItemMapping]) -> PopulationResult:
        """Fill client BOQ template with selected prices."""
        pass

    async def calculate_indirects(self, project: Project,
                                   template_path: str) -> IndirectsResult:
        """Calculate indirects using historical data."""
        pass

    async def benchmark_price(self, item: BOQItem) -> BenchmarkResult:
        """Get historical price range for item."""
        pass

    async def generate_gaps_report(self, project_id: int) -> bytes:
        """Generate pricing gaps Excel report."""
        pass
```

---

## 7. AI/LLM Integration

### 7.1 Hybrid LLM Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM Router                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Incoming Request                                                          │
│         │                                                                    │
│         ▼                                                                    │
│   ┌───────────────┐                                                         │
│   │ Classify Task │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│     ┌─────┴─────┐                                                           │
│     │           │                                                            │
│     ▼           ▼                                                            │
│  Simple     Complex                                                          │
│  Tasks      Tasks                                                            │
│     │           │                                                            │
│     ▼           ▼                                                            │
│  ┌──────┐   ┌──────────┐                                                    │
│  │Ollama│   │ OpenAI   │                                                    │
│  │Local │   │ GPT-4o   │                                                    │
│  └──────┘   └──────────┘                                                    │
│                                                                              │
│  Simple Tasks (Local):           Complex Tasks (Cloud):                     │
│  - Text classification           - Project summary extraction               │
│  - Keyword extraction            - Requirements analysis                    │
│  - Basic categorization          - Offer compliance checking                │
│  - Template filling              - Clarification drafting                   │
│  - Simple Q&A                    - Complex document understanding           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 LangGraph Agent Architecture

```python
# agents/base.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from operator import add

class AgentState(TypedDict):
    project_id: int
    messages: Annotated[list, add]
    documents: list
    current_step: str
    results: dict
    errors: list

# agents/archivist.py
class ArchivistAgent:
    """
    Agent responsible for document understanding and indexing.

    Capabilities:
    - Parse any document type
    - Extract metadata
    - Generate embeddings
    - Answer document-based questions
    """

    def __init__(self, llm, document_service, vector_store):
        self.llm = llm
        self.doc_service = document_service
        self.vector_store = vector_store
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("parse_documents", self.parse_documents)
        graph.add_node("extract_metadata", self.extract_metadata)
        graph.add_node("generate_embeddings", self.generate_embeddings)
        graph.add_node("validate_index", self.validate_index)

        graph.set_entry_point("parse_documents")
        graph.add_edge("parse_documents", "extract_metadata")
        graph.add_edge("extract_metadata", "generate_embeddings")
        graph.add_edge("generate_embeddings", "validate_index")
        graph.add_edge("validate_index", END)

        return graph.compile()

    async def parse_documents(self, state: AgentState) -> AgentState:
        """Parse all documents in project folder."""
        pass

    async def extract_metadata(self, state: AgentState) -> AgentState:
        """Extract metadata from parsed documents."""
        pass

    async def generate_embeddings(self, state: AgentState) -> AgentState:
        """Generate vector embeddings for search."""
        pass

    async def validate_index(self, state: AgentState) -> AgentState:
        """Validate index completeness."""
        pass
```

### 7.3 Prompt Templates

```python
# prompts/project_summary.py

PROJECT_SUMMARY_PROMPT = """
You are an expert construction project analyst. Extract the following information from the tender documents.

For each field:
1. Extract the exact value found in documents
2. Provide a confidence score (0.0-1.0)
3. Cite the source with document name, page/section, and relevant snippet

If a field cannot be found, set value to null and confidence to 0.

## Fields to Extract:

1. **project_name**: Official project name
2. **project_owner**: The entity issuing the tender (client/employer)
3. **main_contractor**: The contractor bidding (if pre-identified)
4. **location**: Project location/site address
5. **key_dates**:
   - ITT release date
   - Clarification deadline
   - Submission deadline
   - Site visit date
   - Validity period
   - Expected award date
6. **scope_of_work**: Brief description of works included
7. **tender_bond**: Required tender bond amount and form
8. **contract_type**: Lump Sum, Remeasured, or Hybrid
9. **contract_conditions**:
   - Form of contract (FIDIC, NEC, etc.)
   - Governing law
   - Liquidated damages
   - Warranty period
   - Insurance requirements
10. **commercial_terms**:
    - Advance payment percentage
    - Performance bond percentage
    - Retention percentage
    - Payment cycle
    - Interim payment rules
11. **sustainability**: LEED/sustainability requirements
12. **consultants**: List of consultants, PMC, designers

## Context Documents:
{context}

## Output Format (JSON):
```json
{{
  "project_name": {{
    "value": "string or null",
    "confidence": 0.0-1.0,
    "evidence": [
      {{
        "document": "filename",
        "page": "page number or section",
        "snippet": "relevant text excerpt"
      }}
    ]
  }},
  ...
}}
```

Extract carefully. Never fabricate information. If unsure, lower the confidence score.
"""
```

```python
# prompts/offer_evaluation.py

OFFER_EVALUATION_PROMPT = """
You are a procurement specialist evaluating a supplier's offer against tender requirements.

## Package Requirements:
{requirements}

## Supplier Offer Content:
{offer_content}

## Tasks:

1. **Price Extraction**: Extract total price, currency, and line item breakdown
2. **Compliance Check**: For each requirement, determine if the offer complies
3. **Exclusions**: List all exclusions mentioned by supplier
4. **Deviations**: List any deviations from specifications
5. **Missing Items**: Identify any required items not quoted
6. **Commercial Terms**: Extract payment terms, validity, delivery time

## Output Format (JSON):
```json
{{
  "total_price": {{
    "amount": number,
    "currency": "string",
    "includes_tax": boolean
  }},
  "line_items": [
    {{
      "description": "string",
      "unit": "string",
      "quantity": number,
      "unit_rate": number,
      "total": number
    }}
  ],
  "compliance": [
    {{
      "requirement": "string",
      "status": "compliant|non_compliant|partial|not_addressed",
      "notes": "string"
    }}
  ],
  "exclusions": ["string"],
  "deviations": [
    {{
      "item": "string",
      "specified": "string",
      "offered": "string",
      "impact": "string"
    }}
  ],
  "missing_items": ["string"],
  "commercial_terms": {{
    "validity_days": number,
    "payment_terms": "string",
    "delivery_weeks": number
  }}
}}
```

Be thorough and precise. Flag any ambiguities.
"""
```

---

## 8. Document Processing Pipeline

### 8.1 Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        Document Processing Pipeline                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Input: Folder Path                                                        │
│         │                                                                   │
│         ▼                                                                   │
│   ┌───────────────────┐                                                    │
│   │   File Discovery  │  Walk directory, filter by extension                │
│   └─────────┬─────────┘                                                    │
│             │                                                               │
│             ▼                                                               │
│   ┌───────────────────┐                                                    │
│   │   Deduplication   │  Hash check, skip unchanged files                   │
│   └─────────┬─────────┘                                                    │
│             │                                                               │
│             ▼                                                               │
│   ┌───────────────────┐      ┌─────────────────────────────────────────┐  │
│   │   Type Detector   │─────▶│  Parser Registry                        │  │
│   └─────────┬─────────┘      │  ├── PDFParser                          │  │
│             │                 │  ├── DocxParser                         │  │
│             │                 │  ├── XlsxParser                         │  │
│             ▼                 │  ├── PptxParser                         │  │
│   ┌───────────────────┐      │  ├── ImageParser (OCR)                  │  │
│   │   Parse Document  │◀─────│  ├── EmailParser (MSG/EML)              │  │
│   └─────────┬─────────┘      │  ├── CADParser (DXF/DWG→DXF)            │  │
│             │                 │  ├── IFCParser                          │  │
│             │                 │  └── XERParser                          │  │
│             ▼                 └─────────────────────────────────────────┘  │
│   ┌───────────────────┐                                                    │
│   │ Language Detection│  Detect Arabic/English/Mixed                       │
│   └─────────┬─────────┘                                                    │
│             │                                                               │
│             ▼                                                               │
│   ┌───────────────────┐                                                    │
│   │   Text Chunking   │  RecursiveCharacterTextSplitter                    │
│   └─────────┬─────────┘  Chunk size: 1000, Overlap: 200                    │
│             │                                                               │
│             ▼                                                               │
│   ┌───────────────────┐                                                    │
│   │   Embedding Gen   │  OpenAI text-embedding-3-small (cloud)             │
│   └─────────┬─────────┘  or all-MiniLM-L6-v2 (local)                       │
│             │                                                               │
│             ▼                                                               │
│   ┌───────────────────┐                                                    │
│   │   Store in Qdrant │  With metadata: project_id, doc_id, page, etc.     │
│   └─────────┬─────────┘                                                    │
│             │                                                               │
│             ▼                                                               │
│   ┌───────────────────┐                                                    │
│   │   Update Database │  Mark document as indexed                          │
│   └───────────────────┘                                                    │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Parser Implementations

```python
# parsers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedContent:
    text: str
    metadata: dict
    pages: Optional[list[str]] = None
    tables: Optional[list[dict]] = None
    images: Optional[list[bytes]] = None

class BaseParser(ABC):
    supported_extensions: list[str] = []

    @abstractmethod
    async def parse(self, file_path: str) -> ParsedContent:
        pass

    @abstractmethod
    async def extract_metadata(self, file_path: str) -> dict:
        pass
```

```python
# parsers/pdf_parser.py
import fitz  # PyMuPDF
from parsers.base import BaseParser, ParsedContent

class PDFParser(BaseParser):
    supported_extensions = ['.pdf']

    async def parse(self, file_path: str) -> ParsedContent:
        doc = fitz.open(file_path)

        pages = []
        full_text = []
        tables = []

        for page_num, page in enumerate(doc):
            # Extract text
            text = page.get_text("text")
            pages.append(text)
            full_text.append(f"[Page {page_num + 1}]\n{text}")

            # Extract tables (basic)
            tabs = page.find_tables()
            for tab in tabs:
                tables.append({
                    "page": page_num + 1,
                    "data": tab.extract()
                })

        # Check if scanned (no text)
        combined_text = "\n".join(full_text)
        if len(combined_text.strip()) < 100:
            # Likely scanned - use OCR
            combined_text = await self._ocr_pdf(file_path)

        return ParsedContent(
            text=combined_text,
            metadata=await self.extract_metadata(file_path),
            pages=pages,
            tables=tables
        )

    async def _ocr_pdf(self, file_path: str) -> str:
        """OCR fallback for scanned PDFs."""
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(file_path)
        text_parts = []

        for i, image in enumerate(images):
            # Arabic + English OCR
            text = pytesseract.image_to_string(image, lang='ara+eng')
            text_parts.append(f"[Page {i + 1}]\n{text}")

        return "\n".join(text_parts)

    async def extract_metadata(self, file_path: str) -> dict:
        doc = fitz.open(file_path)
        meta = doc.metadata
        return {
            "title": meta.get("title"),
            "author": meta.get("author"),
            "subject": meta.get("subject"),
            "creator": meta.get("creator"),
            "creation_date": meta.get("creationDate"),
            "page_count": len(doc)
        }
```

---

## 9. CAD/BIM File Handling

### 9.1 CAD Processing Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAD/BIM Processing Pipeline                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   DWG Files                      DXF Files                    IFC Files     │
│       │                              │                            │         │
│       ▼                              │                            │         │
│   ┌───────────────┐                  │                            │         │
│   │  ODA File     │                  │                            │         │
│   │  Converter    │                  │                            │         │
│   │  (External)   │                  │                            │         │
│   └───────┬───────┘                  │                            │         │
│           │                          │                            │         │
│           ▼                          ▼                            │         │
│   ┌─────────────────────────────────────────┐                     │         │
│   │              DXF Parser (ezdxf)         │                     │         │
│   │  ┌─────────────────────────────────┐    │                     │         │
│   │  │ Extract:                        │    │                     │         │
│   │  │ - Layer names                   │    │                     │         │
│   │  │ - Block definitions             │    │                     │         │
│   │  │ - Text entities (MTEXT, TEXT)   │    │                     │         │
│   │  │ - Dimensions                    │    │                     │         │
│   │  │ - Attribute values              │    │                     │         │
│   │  │ - Title block info              │    │                     │         │
│   │  └─────────────────────────────────┘    │                     │         │
│   └─────────────────────────────────────────┘                     │         │
│                                                                    │         │
│   ┌────────────────────────────────────────────────────────────────┘         │
│   │                                                                          │
│   ▼                                                                          │
│   ┌─────────────────────────────────────────┐                                │
│   │           IFC Parser (ifcopenshell)     │                                │
│   │  ┌─────────────────────────────────┐    │                                │
│   │  │ Extract:                        │    │                                │
│   │  │ - Project info                  │    │                                │
│   │  │ - Building elements             │    │                                │
│   │  │ - Material schedules            │    │                                │
│   │  │ - Quantities (QTO)              │    │                                │
│   │  │ - Property sets                 │    │                                │
│   │  │ - Spatial hierarchy             │    │                                │
│   │  └─────────────────────────────────┘    │                                │
│   └─────────────────────────────────────────┘                                │
│                                                                              │
│   Output: Structured JSON + Searchable Text                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 DWG Conversion Setup

```yaml
# config/cad_processing.yaml

dwg_converter:
  # ODA File Converter (free from opendesign.com)
  executable: "C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe"
  input_format: "DWG"
  output_format: "DXF"
  output_version: "2018"  # AutoCAD 2018 DXF format

  # Batch conversion command template
  command_template: >
    "{executable}" "{input_folder}" "{output_folder}"
    "ACAD{output_version}" "DXF" "0" "1"

dxf_extraction:
  extract_text: true
  extract_dimensions: true
  extract_blocks: true
  layer_filter: null  # Extract from all layers, or specify list

ifc_extraction:
  extract_quantities: true
  extract_materials: true
  extract_properties: true
  element_types:
    - IfcWall
    - IfcSlab
    - IfcBeam
    - IfcColumn
    - IfcDoor
    - IfcWindow
    - IfcPipeSegment
    - IfcDuctSegment
```

### 9.3 CAD Parser Implementation

```python
# parsers/cad_parser.py
import ezdxf
import subprocess
import tempfile
from pathlib import Path
from parsers.base import BaseParser, ParsedContent

class CADParser(BaseParser):
    supported_extensions = ['.dwg', '.dxf']

    def __init__(self, config):
        self.converter_path = config.get("dwg_converter.executable")

    async def parse(self, file_path: str) -> ParsedContent:
        path = Path(file_path)

        # Convert DWG to DXF if needed
        if path.suffix.lower() == '.dwg':
            dxf_path = await self._convert_dwg_to_dxf(file_path)
        else:
            dxf_path = file_path

        # Parse DXF
        doc = ezdxf.readfile(dxf_path)

        extracted_text = []
        metadata = {
            "layers": [],
            "blocks": [],
            "title_block": {}
        }

        # Extract layer names
        for layer in doc.layers:
            metadata["layers"].append(layer.dxf.name)

        # Extract text entities
        msp = doc.modelspace()

        for entity in msp.query("TEXT MTEXT"):
            text = entity.dxf.text if hasattr(entity.dxf, 'text') else entity.text
            extracted_text.append(text)

        # Extract dimension values
        for dim in msp.query("DIMENSION"):
            if hasattr(dim, 'get_measurement'):
                value = dim.get_measurement()
                extracted_text.append(f"Dimension: {value}")

        # Extract block attributes (often contain drawing info)
        for insert in msp.query("INSERT"):
            block_name = insert.dxf.name
            metadata["blocks"].append(block_name)

            for attrib in insert.attribs:
                tag = attrib.dxf.tag
                value = attrib.dxf.text
                extracted_text.append(f"{tag}: {value}")

                # Title block detection
                if any(k in tag.lower() for k in ['title', 'dwg', 'rev', 'date', 'scale']):
                    metadata["title_block"][tag] = value

        return ParsedContent(
            text="\n".join(extracted_text),
            metadata=metadata
        )

    async def _convert_dwg_to_dxf(self, dwg_path: str) -> str:
        """Convert DWG to DXF using ODA File Converter."""
        input_dir = Path(dwg_path).parent
        output_dir = tempfile.mkdtemp()

        cmd = [
            self.converter_path,
            str(input_dir),
            output_dir,
            "ACAD2018",
            "DXF",
            "0",  # Recurse: 0 = no
            "1"   # Audit: 1 = yes
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        # Find converted file
        dxf_name = Path(dwg_path).stem + ".dxf"
        return str(Path(output_dir) / dxf_name)

    async def extract_metadata(self, file_path: str) -> dict:
        content = await self.parse(file_path)
        return content.metadata
```

### 9.4 IFC Parser Implementation

```python
# parsers/ifc_parser.py
import ifcopenshell
import ifcopenshell.util.element
from parsers.base import BaseParser, ParsedContent

class IFCParser(BaseParser):
    supported_extensions = ['.ifc']

    async def parse(self, file_path: str) -> ParsedContent:
        ifc_file = ifcopenshell.open(file_path)

        extracted_text = []
        metadata = {
            "project": {},
            "elements": [],
            "quantities": [],
            "materials": []
        }

        # Extract project info
        project = ifc_file.by_type("IfcProject")[0]
        metadata["project"] = {
            "name": project.Name,
            "description": project.Description
        }
        extracted_text.append(f"Project: {project.Name}")

        # Extract building elements
        element_types = [
            "IfcWall", "IfcSlab", "IfcBeam", "IfcColumn",
            "IfcDoor", "IfcWindow", "IfcPipeSegment", "IfcDuctSegment"
        ]

        for element_type in element_types:
            elements = ifc_file.by_type(element_type)
            for elem in elements:
                elem_info = {
                    "type": element_type,
                    "name": elem.Name,
                    "global_id": elem.GlobalId
                }

                # Get properties
                psets = ifcopenshell.util.element.get_psets(elem)
                elem_info["properties"] = psets

                # Get quantities
                qtos = ifcopenshell.util.element.get_qtos(elem)
                if qtos:
                    for qto_name, quantities in qtos.items():
                        for q_name, q_value in quantities.items():
                            metadata["quantities"].append({
                                "element": elem.Name,
                                "quantity_set": qto_name,
                                "name": q_name,
                                "value": q_value
                            })

                metadata["elements"].append(elem_info)
                extracted_text.append(f"{element_type}: {elem.Name}")

        # Extract materials
        for material in ifc_file.by_type("IfcMaterial"):
            metadata["materials"].append(material.Name)
            extracted_text.append(f"Material: {material.Name}")

        return ParsedContent(
            text="\n".join(extracted_text),
            metadata=metadata
        )

    async def extract_metadata(self, file_path: str) -> dict:
        content = await self.parse(file_path)
        return content.metadata
```

### 9.5 Primavera XER Parser

```python
# parsers/xer_parser.py
from parsers.base import BaseParser, ParsedContent
from typing import Dict, List
import re

class XERParser(BaseParser):
    """Parser for Primavera P6 XER export files."""

    supported_extensions = ['.xer']

    async def parse(self, file_path: str) -> ParsedContent:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        tables = self._parse_xer_tables(content)

        extracted_text = []
        metadata = {
            "projects": [],
            "activities": [],
            "resources": [],
            "wbs": []
        }

        # Extract project info
        if "PROJECT" in tables:
            for proj in tables["PROJECT"]["data"]:
                proj_dict = dict(zip(tables["PROJECT"]["columns"], proj))
                metadata["projects"].append({
                    "id": proj_dict.get("proj_id"),
                    "name": proj_dict.get("proj_short_name"),
                    "start": proj_dict.get("plan_start_date"),
                    "finish": proj_dict.get("plan_end_date")
                })
                extracted_text.append(f"Project: {proj_dict.get('proj_short_name')}")

        # Extract activities
        if "TASK" in tables:
            for task in tables["TASK"]["data"]:
                task_dict = dict(zip(tables["TASK"]["columns"], task))
                metadata["activities"].append({
                    "id": task_dict.get("task_id"),
                    "code": task_dict.get("task_code"),
                    "name": task_dict.get("task_name"),
                    "start": task_dict.get("act_start_date") or task_dict.get("early_start_date"),
                    "finish": task_dict.get("act_end_date") or task_dict.get("early_end_date"),
                    "duration": task_dict.get("target_drtn_hr_cnt")
                })
                extracted_text.append(f"Activity: {task_dict.get('task_code')} - {task_dict.get('task_name')}")

        # Extract WBS
        if "PROJWBS" in tables:
            for wbs in tables["PROJWBS"]["data"]:
                wbs_dict = dict(zip(tables["PROJWBS"]["columns"], wbs))
                metadata["wbs"].append({
                    "id": wbs_dict.get("wbs_id"),
                    "code": wbs_dict.get("wbs_short_name"),
                    "name": wbs_dict.get("wbs_name")
                })

        return ParsedContent(
            text="\n".join(extracted_text),
            metadata=metadata
        )

    def _parse_xer_tables(self, content: str) -> Dict[str, dict]:
        """Parse XER file into table structures."""
        tables = {}
        current_table = None
        columns = []

        for line in content.split('\n'):
            line = line.strip()

            if line.startswith('%T'):
                # Table definition
                current_table = line[3:].strip()
                tables[current_table] = {"columns": [], "data": []}

            elif line.startswith('%F') and current_table:
                # Field definitions
                columns = line[3:].strip().split('\t')
                tables[current_table]["columns"] = columns

            elif line.startswith('%R') and current_table:
                # Data row
                values = line[3:].strip().split('\t')
                tables[current_table]["data"].append(values)

        return tables

    async def extract_metadata(self, file_path: str) -> dict:
        content = await self.parse(file_path)
        return content.metadata
```

---

## 10. Security & Authentication

### 10.1 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Authentication Flow                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. Login Request                                                           │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐           │
│   │   Client    │────────▶│   FastAPI   │────────▶│  PostgreSQL │           │
│   │             │ email   │   /login    │ verify  │   users     │           │
│   │             │ password│             │ hash    │             │           │
│   └─────────────┘         └─────────────┘         └─────────────┘           │
│                                  │                                           │
│                                  ▼                                           │
│   2. Token Generation      ┌─────────────┐                                  │
│                            │   JWT       │                                   │
│                            │  Generate   │                                   │
│                            │  ├── access_token (15 min)                     │
│                            │  └── refresh_token (7 days)                    │
│                            └──────┬──────┘                                  │
│                                   │                                          │
│                                   ▼                                          │
│   3. Token Response        ┌─────────────┐                                  │
│                            │   Client    │                                   │
│                            │  stores in  │                                   │
│                            │  httpOnly   │                                   │
│                            │  cookie     │                                   │
│                            └─────────────┘                                  │
│                                                                              │
│   4. Authenticated Requests                                                  │
│   ┌─────────────┐  Bearer Token  ┌─────────────┐                            │
│   │   Client    │───────────────▶│   FastAPI   │                            │
│   │             │                │  Middleware │                            │
│   │             │◀───────────────│  validates  │                            │
│   └─────────────┘  Response      └─────────────┘                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Role-Based Access Control

```python
# auth/permissions.py
from enum import Enum
from typing import Set

class Permission(Enum):
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"

    # Document permissions
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE = "document:delete"

    # Package permissions
    PACKAGE_CREATE = "package:create"
    PACKAGE_SEND = "package:send"

    # Supplier permissions
    SUPPLIER_MANAGE = "supplier:manage"

    # Offer permissions
    OFFER_UPLOAD = "offer:upload"
    OFFER_EVALUATE = "offer:evaluate"

    # Pricing permissions
    PRICING_POPULATE = "pricing:populate"
    PRICING_APPROVE = "pricing:approve"

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_SETTINGS = "admin:settings"

class Role(Enum):
    ADMIN = "admin"
    TENDER_MANAGER = "tender_manager"
    ESTIMATOR = "estimator"
    VIEWER = "viewer"

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions

    Role.TENDER_MANAGER: {
        Permission.PROJECT_CREATE,
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.PACKAGE_CREATE,
        Permission.PACKAGE_SEND,
        Permission.SUPPLIER_MANAGE,
        Permission.OFFER_UPLOAD,
        Permission.OFFER_EVALUATE,
        Permission.PRICING_POPULATE,
        Permission.PRICING_APPROVE,
    },

    Role.ESTIMATOR: {
        Permission.PROJECT_READ,
        Permission.DOCUMENT_READ,
        Permission.PACKAGE_CREATE,
        Permission.OFFER_UPLOAD,
        Permission.OFFER_EVALUATE,
        Permission.PRICING_POPULATE,
    },

    Role.VIEWER: {
        Permission.PROJECT_READ,
        Permission.DOCUMENT_READ,
    },
}
```

### 10.3 Credential Storage

```python
# auth/credentials.py
from cryptography.fernet import Fernet
from pathlib import Path
import json
import os

class CredentialManager:
    """Secure storage for API keys and credentials."""

    def __init__(self, key_file: str = ".bidops_key"):
        self.key_file = Path(key_file)
        self.creds_file = Path(".bidops_credentials.enc")
        self._key = self._load_or_create_key()
        self._fernet = Fernet(self._key)

    def _load_or_create_key(self) -> bytes:
        if self.key_file.exists():
            return self.key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            # Restrict permissions (Windows: use icacls)
            os.chmod(self.key_file, 0o600)
            return key

    def store_credential(self, name: str, value: str):
        """Store an encrypted credential."""
        creds = self._load_credentials()
        creds[name] = value
        self._save_credentials(creds)

    def get_credential(self, name: str) -> str | None:
        """Retrieve a decrypted credential."""
        creds = self._load_credentials()
        return creds.get(name)

    def _load_credentials(self) -> dict:
        if not self.creds_file.exists():
            return {}
        encrypted = self.creds_file.read_bytes()
        decrypted = self._fernet.decrypt(encrypted)
        return json.loads(decrypted)

    def _save_credentials(self, creds: dict):
        data = json.dumps(creds).encode()
        encrypted = self._fernet.encrypt(data)
        self.creds_file.write_bytes(encrypted)
        os.chmod(self.creds_file, 0o600)
```

### 10.4 Audit Trail

```python
# models/audit.py
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user_email: Mapped[str] = mapped_column(String(255))

    action: Mapped[str] = mapped_column(String(100))  # create, update, delete, login, etc.
    entity_type: Mapped[str] = mapped_column(String(100))  # project, document, offer, etc.
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)

    old_value: Mapped[Optional[dict]] = mapped_column(JSON)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON)

    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

# services/audit_service.py
class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: int,
        user_email: str,
        action: str,
        entity_type: str,
        entity_id: int = None,
        old_value: dict = None,
        new_value: dict = None,
        request: Request = None
    ):
        log = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        self.db.add(log)
        await self.db.commit()
```

---

## 11. Deployment Architecture

### 11.1 Local Network Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Local Network Deployment                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │                         Windows Server                                 │ │
│   │                                                                        │ │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │ │
│   │   │   Nginx     │  │   FastAPI   │  │   Ollama    │                   │ │
│   │   │   :443      │──│   :8000     │  │   :11434    │                   │ │
│   │   │   SSL       │  │   (x3)      │  │   LLM       │                   │ │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                   │ │
│   │                                                                        │ │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │ │
│   │   │  PostgreSQL │  │   Qdrant    │  │    Redis    │                   │ │
│   │   │   :5432     │  │   :6333     │  │    :6379    │                   │ │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                   │ │
│   │                                                                        │ │
│   │   ┌─────────────────────────────────────────────────────────────┐     │ │
│   │   │                    Shared File Storage                       │     │ │
│   │   │   D:\BidOps\                                                │     │ │
│   │   │   ├── projects\                                             │     │ │
│   │   │   ├── database\                                             │     │ │
│   │   │   └── temp\                                                 │     │ │
│   │   └─────────────────────────────────────────────────────────────┘     │ │
│   │                                                                        │ │
│   └───────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    │ LAN (https://bidops.local)             │
│                                    │                                         │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐               │
│   │  Workstation 1 │  │  Workstation 2 │  │  Workstation N │               │
│   │  (Tender Mgr)  │  │  (Estimator)   │  │  (Viewer)      │               │
│   │  ┌──────────┐  │  │  ┌──────────┐  │  │  ┌──────────┐  │               │
│   │  │ Browser  │  │  │  │ Browser  │  │  │  │ Browser  │  │               │
│   │  │  or      │  │  │  │  or      │  │  │  │  or      │  │               │
│   │  │ Electron │  │  │  │ Electron │  │  │  │ Electron │  │               │
│   │  └──────────┘  │  │  └──────────┘  │  │  └──────────┘  │               │
│   └────────────────┘  └────────────────┘  └────────────────┘               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - api
    restart: unless-stopped

  # FastAPI Backend (multiple instances for load balancing)
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      - DATABASE_URL=postgresql+asyncpg://bidops:${DB_PASSWORD}@postgres:5432/bidops
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_URL=http://ollama:11434
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - ./storage:/app/storage
    depends_on:
      - postgres
      - redis
      - qdrant
    deploy:
      replicas: 3
    restart: unless-stopped

  # Background Worker
  worker:
    build:
      context: .
      dockerfile: Dockerfile.api
    command: arq app.worker.WorkerSettings
    environment:
      - DATABASE_URL=postgresql+asyncpg://bidops:${DB_PASSWORD}@postgres:5432/bidops
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_URL=http://ollama:11434
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./storage:/app/storage
    depends_on:
      - postgres
      - redis
      - qdrant
    restart: unless-stopped

  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=bidops
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=bidops
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  # Redis Cache & Queue
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Qdrant Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  # Ollama (Local LLM) - Optional
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]  # Enable GPU if available
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  ollama_data:
```

### 11.3 Nginx Configuration

```nginx
# nginx/nginx.conf

upstream api_servers {
    least_conn;
    server api:8000 weight=1;
}

server {
    listen 80;
    server_name bidops.local;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bidops.local;

    ssl_certificate /etc/nginx/ssl/bidops.crt;
    ssl_certificate_key /etc/nginx/ssl/bidops.key;

    # API endpoints
    location /api/ {
        proxy_pass http://api_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running operations
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # WebSocket for real-time updates
    location /ws/ {
        proxy_pass http://api_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files (frontend)
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # Upload size limit (for large documents)
    client_max_body_size 500M;
}
```

---

## 12. File Structure

```
bidops-ai/
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── build.yml
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── nginx/
│   ├── nginx.conf
│   └── ssl/
├── docs/
│   ├── TECHNICAL_SPECIFICATION.md
│   ├── API_REFERENCE.md
│   ├── DEPLOYMENT_GUIDE.md
│   └── USER_MANUAL.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry
│   │   ├── config.py                  # Settings management
│   │   ├── database.py                # DB connection
│   │   │
│   │   ├── api/                       # API Layer
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                # Dependencies (auth, db)
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── packages.py
│   │   │   │   ├── suppliers.py
│   │   │   │   ├── offers.py
│   │   │   │   ├── pricing.py
│   │   │   │   └── auth.py
│   │   │   └── websocket.py
│   │   │
│   │   ├── models/                    # SQLAlchemy Models
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── document.py
│   │   │   ├── boq.py
│   │   │   ├── package.py
│   │   │   ├── supplier.py
│   │   │   ├── offer.py
│   │   │   └── audit.py
│   │   │
│   │   ├── schemas/                   # Pydantic Schemas
│   │   │   ├── __init__.py
│   │   │   ├── project.py
│   │   │   ├── document.py
│   │   │   ├── package.py
│   │   │   ├── supplier.py
│   │   │   ├── offer.py
│   │   │   └── auth.py
│   │   │
│   │   ├── services/                  # Business Logic
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py
│   │   │   ├── ai_service.py
│   │   │   ├── packaging_service.py
│   │   │   ├── supplier_service.py
│   │   │   ├── email_service.py
│   │   │   ├── evaluation_service.py
│   │   │   ├── pricing_service.py
│   │   │   └── audit_service.py
│   │   │
│   │   ├── agents/                    # LangGraph Agents
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── archivist.py
│   │   │   ├── qs_agent.py
│   │   │   ├── procurement.py
│   │   │   ├── evaluator.py
│   │   │   └── estimator.py
│   │   │
│   │   ├── parsers/                   # Document Parsers
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── pdf_parser.py
│   │   │   ├── docx_parser.py
│   │   │   ├── xlsx_parser.py
│   │   │   ├── pptx_parser.py
│   │   │   ├── email_parser.py
│   │   │   ├── image_parser.py
│   │   │   ├── cad_parser.py
│   │   │   ├── ifc_parser.py
│   │   │   └── xer_parser.py
│   │   │
│   │   ├── prompts/                   # LLM Prompts
│   │   │   ├── __init__.py
│   │   │   ├── project_summary.py
│   │   │   ├── checklist.py
│   │   │   ├── classification.py
│   │   │   ├── evaluation.py
│   │   │   └── clarification.py
│   │   │
│   │   ├── auth/                      # Authentication
│   │   │   ├── __init__.py
│   │   │   ├── jwt.py
│   │   │   ├── permissions.py
│   │   │   └── credentials.py
│   │   │
│   │   └── utils/                     # Utilities
│   │       ├── __init__.py
│   │       ├── file_utils.py
│   │       ├── excel_utils.py
│   │       └── pdf_generator.py
│   │
│   ├── migrations/                    # Alembic Migrations
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   │
│   ├── tests/                         # Tests
│   │   ├── conftest.py
│   │   ├── test_parsers/
│   │   ├── test_services/
│   │   ├── test_api/
│   │   └── test_agents/
│   │
│   ├── worker.py                      # ARQ Worker
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                   # React entry
│   │   ├── App.tsx
│   │   ├── index.css
│   │   │
│   │   ├── components/                # UI Components
│   │   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Layout.tsx
│   │   │   ├── project/
│   │   │   │   ├── ProjectWizard.tsx
│   │   │   │   ├── ProjectCard.tsx
│   │   │   │   └── ProjectSummary.tsx
│   │   │   ├── document/
│   │   │   │   ├── DocumentBrowser.tsx
│   │   │   │   └── DocumentViewer.tsx
│   │   │   ├── package/
│   │   │   │   ├── PackageList.tsx
│   │   │   │   └── PackageDetails.tsx
│   │   │   ├── supplier/
│   │   │   │   └── SupplierTable.tsx
│   │   │   ├── offer/
│   │   │   │   ├── OfferUpload.tsx
│   │   │   │   └── ComparisonMatrix.tsx
│   │   │   └── pricing/
│   │   │       ├── BOQEditor.tsx
│   │   │       └── GapsReport.tsx
│   │   │
│   │   ├── pages/                     # Page Components
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Projects.tsx
│   │   │   ├── ProjectDetail.tsx
│   │   │   ├── Packages.tsx
│   │   │   ├── Suppliers.tsx
│   │   │   ├── Offers.tsx
│   │   │   ├── Pricing.tsx
│   │   │   ├── Settings.tsx
│   │   │   └── Login.tsx
│   │   │
│   │   ├── hooks/                     # Custom Hooks
│   │   │   ├── useAuth.ts
│   │   │   ├── useProject.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── useQuery.ts
│   │   │
│   │   ├── stores/                    # Zustand Stores
│   │   │   ├── authStore.ts
│   │   │   ├── projectStore.ts
│   │   │   └── uiStore.ts
│   │   │
│   │   ├── services/                  # API Client
│   │   │   ├── api.ts
│   │   │   ├── projects.ts
│   │   │   ├── documents.ts
│   │   │   └── websocket.ts
│   │   │
│   │   ├── types/                     # TypeScript Types
│   │   │   ├── project.ts
│   │   │   ├── document.ts
│   │   │   ├── package.ts
│   │   │   └── api.ts
│   │   │
│   │   └── utils/                     # Utilities
│   │       ├── format.ts
│   │       └── validation.ts
│   │
│   ├── electron/                      # Electron Shell
│   │   ├── main.ts
│   │   ├── preload.ts
│   │   └── ipc.ts
│   │
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── electron-builder.json
│   ├── package.json
│   └── tsconfig.json
│
├── storage/                           # Data Storage (gitignored)
│   ├── projects/
│   ├── database/
│   │   └── historical/
│   └── temp/
│
├── templates/                         # Default Templates
│   ├── email/
│   │   ├── rfq_en.html
│   │   ├── rfq_ar.html
│   │   ├── clarification_en.html
│   │   └── clarification_ar.html
│   ├── excel/
│   │   ├── comparison_matrix.xlsx
│   │   ├── package_register.xlsx
│   │   └── gaps_report.xlsx
│   └── config/
│       └── default_rules.yaml
│
├── scripts/
│   ├── setup.sh
│   ├── setup.ps1
│   └── seed_data.py
│
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

---

## 13. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**
- [ ] Project structure setup
- [ ] Database models and migrations
- [ ] FastAPI backend with basic CRUD
- [ ] Authentication system (JWT)
- [ ] Basic React frontend with routing
- [ ] Docker development environment

**Technical Tasks:**
1. Initialize backend with FastAPI, SQLAlchemy 2.0, Pydantic 2.0
2. Set up PostgreSQL, Redis, Qdrant with Docker Compose
3. Implement user authentication with role-based access
4. Create frontend scaffolding with Vite, React, TypeScript
5. Set up CI/CD pipeline for testing

### Phase 2: Document Processing (Weeks 3-4)

**Deliverables:**
- [ ] All parsers implemented (PDF, DOCX, XLSX, etc.)
- [ ] OCR for scanned documents
- [ ] Vector embedding generation
- [ ] Semantic search functionality
- [ ] Document browser UI

**Technical Tasks:**
1. Implement parser classes for each file type
2. Integrate pytesseract for OCR
3. Connect to Qdrant for vector storage
4. Build document upload and browse UI
5. Implement incremental indexing

### Phase 3: AI Extraction (Weeks 5-6)

**Deliverables:**
- [ ] Project summary extraction with citations
- [ ] Requirements checklist generation
- [ ] Hybrid LLM strategy (local + cloud)
- [ ] Human review UI for low-confidence items

**Technical Tasks:**
1. Design and test extraction prompts
2. Implement LangGraph agent for summary extraction
3. Set up Ollama for local LLM fallback
4. Build review/approval screens in frontend
5. Add confidence thresholds and escalation

### Phase 4: CAD/BIM Support (Weeks 7-8)

**Deliverables:**
- [ ] DXF parsing with ezdxf
- [ ] DWG conversion pipeline (ODA)
- [ ] IFC parsing with ifcopenshell
- [ ] XER/XML Primavera parsing
- [ ] CAD metadata extraction

**Technical Tasks:**
1. Set up ODA File Converter for DWG→DXF
2. Implement DXF text and attribute extraction
3. Implement IFC element and quantity extraction
4. Build XER parser for schedule data
5. Integrate CAD data into search index

### Phase 5: Packaging (Weeks 9-10)

**Deliverables:**
- [ ] BOQ parsing and standardization
- [ ] Intelligent item classification
- [ ] Package creation with document linking
- [ ] Package folder generation
- [ ] Package brief PDF generation

**Technical Tasks:**
1. Build flexible BOQ Excel parser
2. Train/test classification prompts
3. Implement document-to-item linking
4. Generate package folders and briefs
5. Create package management UI

### Phase 6: Supplier Management (Weeks 11-12)

**Deliverables:**
- [ ] Supplier database with Excel import
- [ ] Microsoft Graph API integration
- [ ] Email template system
- [ ] RFQ sending with logging
- [ ] Draft mode support

**Technical Tasks:**
1. Implement supplier CRUD and import
2. Set up OAuth for Microsoft Graph
3. Build email template renderer (Jinja2)
4. Implement email sending with retry
5. Create email log and tracking UI

### Phase 7: Offer Evaluation (Weeks 13-14)

**Deliverables:**
- [ ] Offer upload and parsing
- [ ] Compliance analysis
- [ ] Clarification email generation
- [ ] Comparison matrix Excel generation
- [ ] Scoring and recommendation

**Technical Tasks:**
1. Build offer parsing for various formats
2. Implement compliance checking logic
3. Generate clarification emails automatically
4. Build comparison matrix generator
5. Implement weighted scoring algorithm

### Phase 8: Pricing & Output (Weeks 15-16)

**Deliverables:**
- [ ] Item mapping (offer → client BOQ)
- [ ] Client BOQ population (preserving formulas)
- [ ] Indirects calculation from historical DB
- [ ] Gaps report generation
- [ ] Final deliverable packaging

**Technical Tasks:**
1. Build intelligent item mapper with LLM
2. Implement template-preserving Excel writing
3. Create historical database integration
4. Generate comprehensive gaps report
5. Build export/download functionality

### Phase 9: Polish & Deployment (Weeks 17-18)

**Deliverables:**
- [ ] Electron desktop app
- [ ] Production deployment scripts
- [ ] Monitoring and logging
- [ ] User documentation
- [ ] Admin dashboard

**Technical Tasks:**
1. Package frontend as Electron app
2. Set up production Docker deployment
3. Add Prometheus/Grafana monitoring
4. Write user manual and admin guide
5. Performance testing and optimization

---

## Appendix A: Hardware Requirements

### Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 8 cores | 16+ cores |
| RAM | 32 GB | 64 GB |
| Storage | 500 GB SSD | 1 TB NVMe |
| GPU (for local LLM) | None | NVIDIA RTX 3090 / A6000 |

### Client Workstation

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB |
| Browser | Chrome/Edge (latest) | Chrome/Edge (latest) |

---

## Appendix B: External Dependencies

### Required Software

1. **ODA File Converter** (free)
   - Download: https://www.opendesign.com/guestfiles/oda_file_converter
   - Purpose: Convert DWG files to DXF

2. **Tesseract OCR**
   - Download: https://github.com/UB-Mannheim/tesseract/wiki
   - Languages: eng, ara

3. **Poppler** (for pdf2image)
   - Windows: https://github.com/oschwartz10612/poppler-windows/releases

### Optional Software

1. **Ollama** (local LLM)
   - Download: https://ollama.ai
   - Models: llama3.1:70b, llama3.1:8b

---

## Appendix C: Configuration Template

```yaml
# config/rules.yaml

# Scoring weights for offer evaluation
scoring:
  weights:
    technical_compliance: 0.30
    price: 0.35
    delivery_time: 0.15
    payment_terms: 0.10
    supplier_rating: 0.10

# Tender keyword detection
keywords:
  mandatory:
    - "must"
    - "shall"
    - "required"
    - "mandatory"
  deadline:
    - "deadline"
    - "due date"
    - "submission"
  bond:
    - "tender bond"
    - "bid bond"
    - "bank guarantee"

# Package sizing rules
packaging:
  min_items_per_package: 5
  max_items_per_package: 100
  grouping_criteria:
    - trade_category
    - spec_section

# Email configuration
email:
  provider: "graph"  # graph, smtp
  from_address: "procurement@company.com"
  reply_to: "procurement@company.com"
  default_language: "en"  # en, ar
  attachment_size_limit_mb: 25

# Naming conventions
naming:
  package_code_format: "PKG-{project_code}-{trade_abbr}-{seq:03d}"
  offer_folder_format: "{package_code}/{supplier_name}"

# Commercial assumptions
commercial:
  currency: "AED"
  vat_rate: 0.05
  default_validity_days: 90
  default_payment_terms: "Net 30"

# Measurement rules
measurement:
  contract_type: "lumpsum"  # lumpsum, remeasured, hybrid
  quantity_tolerance: 0.05  # 5% tolerance for quantity matching

# LLM settings
llm:
  cloud_provider: "openai"
  cloud_model: "gpt-4o"
  local_provider: "ollama"
  local_model: "llama3.1:70b"
  use_local_for:
    - "classification"
    - "simple_extraction"
  confidence_threshold: 0.7
  require_review_below: 0.5
```

---

**End of Technical Specification**
