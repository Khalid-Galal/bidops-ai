# BidOps AI

**Production-grade tender/bidding automation system for contracting companies**

## 🚀 Deploy Now!

**Choose your deployment method:**

- **[🆓 Free Deployment (Render.com)](./DEPLOY-QUICK-START.md#-step-a-deploy-free-on-rendercom-5-minutes)** - 5 minutes, perfect for demos
- **[🖥️ VPS Deployment](./DEPLOY-QUICK-START.md#%EF%B8%8F-step-b-deploy-on-vps-production)** - 30 minutes, production-ready
- **[📋 One-Page Cheat Sheet](./DEPLOYMENT-CHEATSHEET.md)** - Quick reference guide
- **[📖 Complete Guide](./DEPLOYMENT-COMPLETE-GUIDE.md)** - All options & details

## Overview

BidOps AI is a desktop+web hybrid application that automates the entire tender/bidding lifecycle:

- 📄 **Document Ingestion** - Parse PDF, DOCX, XLSX, CAD (DWG/DXF), BIM (IFC), Primavera (XER), and more
- 🔍 **Intelligent Extraction** - Extract project metadata, requirements, and deadlines with AI
- 📦 **Smart Packaging** - Group BOQ items and link relevant specs/drawings automatically
- 📧 **Supplier Management** - Send RFQs, track responses, automate follow-ups
- ⚖️ **Offer Evaluation** - Compare offers, check compliance, generate clarifications
- 💰 **Pricing Automation** - Populate client BOQ templates with selected prices

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Node.js 20+ (for frontend)
- Docker & Docker Compose (recommended)

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/bidops-ai.git
cd bidops-ai

# Backend setup
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Copy environment file
copy .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Docker Setup (Recommended)

```bash
# Start all services
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Electron + React + TypeScript)                   │
├─────────────────────────────────────────────────────────────┤
│  FastAPI Backend                                            │
│  ├── REST API + WebSocket                                   │
│  ├── Core Services (Document, AI, Packaging, Email, etc.)  │
│  └── LangGraph Agents (Archivist, QS, Procurement, etc.)   │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                 │
│  ├── PostgreSQL (Structured data)                          │
│  ├── Qdrant (Vector embeddings)                            │
│  └── Redis (Cache + Task queue)                            │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### Document Processing

| Format | Support Level | Notes |
|--------|--------------|-------|
| PDF | ✅ Full | Text extraction + OCR for scanned |
| DOCX | ✅ Full | Text, tables, metadata |
| XLSX | ✅ Full | Data, formulas (preserved on write) |
| PPTX | ✅ Full | Text, notes |
| MSG/EML | ✅ Full | Email content + attachments |
| DWG | ✅ Full | Via ODA converter → DXF |
| DXF | ✅ Full | Native parsing with ezdxf |
| IFC | ✅ Full | BIM data with ifcopenshell |
| XER/XML | ✅ Full | Primavera schedule data |
| Images | ✅ Full | OCR with Tesseract |

### AI/LLM Integration

- **Cloud LLM**: OpenAI GPT-4o for complex extraction
- **Local LLM**: Ollama (Llama 3.1) for offline/simple tasks
- **Hybrid Strategy**: Automatic routing based on task complexity

### Multilingual Support

- English and Arabic fully supported
- Auto-detection of document language
- Bilingual email templates

## Configuration

Edit `config/rules.yaml` to customize:

```yaml
scoring:
  weights:
    technical_compliance: 0.30
    price: 0.35
    delivery_time: 0.15
    payment_terms: 0.10
    supplier_rating: 0.10

packaging:
  min_items_per_package: 5
  max_items_per_package: 100

commercial:
  currency: "AED"
  vat_rate: 0.05
```

## Documentation

- [Technical Specification](docs/TECHNICAL_SPECIFICATION.md) - Complete system design
- [API Reference](docs/API_REFERENCE.md) - Endpoint documentation
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Production setup
- [User Manual](docs/USER_MANUAL.md) - End-user guide

## Project Structure

```
bidops-ai/
├── backend/           # Python FastAPI backend
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── models/    # Database models
│   │   ├── services/  # Business logic
│   │   ├── agents/    # LangGraph agents
│   │   ├── parsers/   # Document parsers
│   │   └── prompts/   # LLM prompts
│   └── tests/
├── frontend/          # React + Electron frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── electron/
├── docs/              # Documentation
├── templates/         # Email/Excel templates
└── docker/            # Docker configuration
```

## External Dependencies

### Required

1. **ODA File Converter** (for DWG files)
   - Download: https://www.opendesign.com/guestfiles/oda_file_converter
   - Free for evaluation/personal use

2. **Tesseract OCR**
   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
   - Install Arabic + English language packs

3. **Poppler** (for PDF to image)
   - Windows: https://github.com/oschwartz10612/poppler-windows/releases

### Optional

1. **Ollama** (for local LLM)
   - Download: https://ollama.ai
   - Recommended models: llama3.1:70b or llama3.1:8b

## License

Proprietary - All rights reserved

## Support

For issues and feature requests, contact the development team.
