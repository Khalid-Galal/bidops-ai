"""FastAPI application entry point with lifespan management."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.boq import router as boq_router
from app.api.checklist import router as checklist_router
from app.api.documents import router as documents_router
from app.api.emails import router as emails_router
from app.api.export import router as export_router
from app.api.extraction import router as extraction_router
from app.api.health import router as health_router
from app.api.packaging import router as packaging_router
from app.api.projects import router as projects_router
from app.api.rules import router as rules_router
from app.api.search import router as search_router
from app.api.suppliers import router as suppliers_router
from app.config import get_settings
from app.database import engine
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Jinja2 template engine (accessible from pages.py via import)
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    settings = get_settings()

    # Startup: create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure required directories exist
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    (Path(__file__).parent / "static" / "css").mkdir(parents=True, exist_ok=True)

    logger.info("BidOps AI started -- database tables created, directories ready")

    yield

    # Shutdown: dispose database engine
    await engine.dispose()
    logger.info("BidOps AI shutdown complete")


settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for local development (v1 is local-only, allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health_router)
app.include_router(projects_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(extraction_router, prefix="/api")
app.include_router(checklist_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(rules_router, prefix="/api")
app.include_router(boq_router, prefix="/api")
app.include_router(packaging_router, prefix="/api")
app.include_router(suppliers_router, prefix="/api")
app.include_router(emails_router, prefix="/api")

# Include page routes (imported here to avoid circular import with templates)
from app.api.pages import router as pages_router  # noqa: E402

app.include_router(pages_router)

# Mount static files (MUST be last -- it's a catch-all mount)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
