"""FastAPI application entry point with lifespan management."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.backup import router as backup_router
from app.api.boq import router as boq_router
from app.api.checklist import router as checklist_router
from app.api.dashboard import router as dashboard_router
from app.api.deliverables import router as deliverables_router
from app.api.documents import router as documents_router
from app.api.emails import router as emails_router
from app.api.export import router as export_router
from app.api.extraction import router as extraction_router
from app.api.health import router as health_router
from app.api.historical import router as historical_router
from app.api.indirects import router as indirects_router
from app.api.offers import router as offers_router
from app.api.packaging import router as packaging_router
from app.api.pricing import router as pricing_router
from app.api.projects import router as projects_router
from app.api.rules import router as rules_router
from app.api.search import router as search_router
from app.api.suppliers import router as suppliers_router
from app.api.versioning import router as versioning_router
from app.config import get_settings
from app.database import engine
from app.errors import register_exception_handlers
from app.middleware import ObservabilityMiddleware, RateLimitMiddleware
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _make_alembic_config():
    """Build an Alembic Config pointing at the shipped migrations/ + alembic.ini.

    Returns None (and logs) when the assets are missing -- e.g. an older image
    that still excluded them -- so startup degrades gracefully instead of
    crashing. Paths and the DB URL are resolved from the app settings/layout so
    the same hook works locally and in the container.
    """
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    ini_path = root / "alembic.ini"
    migrations_dir = root / "migrations"
    if not ini_path.exists() or not migrations_dir.exists():
        logger.warning(
            "Alembic assets missing (alembic.ini / migrations/) -- skipping "
            "migrations"
        )
        return None
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option(
        "sqlalchemy.url", f"sqlite+aiosqlite:///{get_settings().database_path}"
    )
    return cfg


def _alembic_upgrade_head() -> None:
    """Bring an EXISTING database up to the latest schema before create_all.

    create_all only adds missing tables; it never ALTERs existing ones, so a DB
    restored from an HF Dataset snapshot / persistent volume needs the migration
    chain replayed. Best effort -- a failure here must never wedge startup.

    Runs the Alembic env (which uses asyncio.run) in a worker thread via the
    caller's asyncio.to_thread, so it must not be invoked on the running loop.
    """
    try:
        from alembic import command

        cfg = _make_alembic_config()
        if cfg is None:
            return
        command.upgrade(cfg, "head")
        logger.info("Alembic: existing database upgraded to head")
    except Exception as exc:  # pragma: no cover - never wedge startup
        logger.warning("Alembic upgrade skipped/failed: %s", exc)


def _alembic_stamp_head() -> None:
    """Stamp a FRESH database (just built by create_all) at head.

    Records the current revision as the baseline so future `upgrade head` runs
    only apply migrations authored after this deploy. Best effort.
    """
    try:
        from alembic import command

        cfg = _make_alembic_config()
        if cfg is None:
            return
        command.stamp(cfg, "head")
        logger.info("Alembic: fresh database stamped at head")
    except Exception as exc:  # pragma: no cover - never wedge startup
        logger.warning("Alembic stamp skipped/failed: %s", exc)

# Jinja2 template engine (accessible from pages.py via import)
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    settings = get_settings()

    # Restore the latest HF Dataset snapshot on a FRESH boot (no-op when the
    # DB file already exists or backups are unconfigured).
    #
    # CRITICAL ORDERING: restore MUST complete before engine.begin() below.
    # The engine is lazy, but once any connection is pooled it is bound to the
    # current DB file; replacing the file underneath it split-brains reads.
    # Never add import-time DB calls in routers/services.
    from app.services.backup.backup_service import (
        RESTORE_TIMEOUT_S,
        get_backup_service,
    )

    backup_svc = get_backup_service()
    if backup_svc.enabled():
        if Path("data").is_symlink():
            logger.info(
                "Persistent disk detected AND HF Dataset snapshots enabled: "
                "snapshots act as an additional off-site backup."
            )
        try:
            # Bounded so a hung HF Hub call can never wedge startup.
            await asyncio.wait_for(
                asyncio.to_thread(backup_svc.restore_sync), timeout=RESTORE_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.warning("Snapshot restore timed out -- starting fresh")

    # Apply schema migrations to a DB restored from a snapshot / volume BEFORE
    # create_all. Capture existence first: engine.begin() below creates the file
    # for fresh installs. The upgrade runs while the app engine is still lazy
    # (no pooled connection yet), preserving the restore-then-bind ordering.
    db_existed = Path(settings.database_path).exists()
    if db_existed:
        await asyncio.to_thread(_alembic_upgrade_head)

    # Startup: create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Fresh DBs are fully built by create_all above; stamp them at head so the
    # migration chain has a baseline for future upgrades.
    if not db_existed:
        await asyncio.to_thread(_alembic_stamp_head)

    # Ensure required directories exist
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    (Path(__file__).parent / "static" / "css").mkdir(parents=True, exist_ok=True)

    logger.info("BidOps AI started -- database tables created, directories ready")

    if settings.warmup_models_on_startup:
        from app.services.indexing.warmup import warmup_models

        asyncio.create_task(asyncio.to_thread(warmup_models))
        logger.info("Model warmup scheduled (background)")

    # Periodic snapshots to the HF Dataset repo whenever data/ changes.
    watcher_task = None
    if backup_svc.enabled():
        watcher_task = asyncio.create_task(backup_svc.watch())

    yield

    # Shutdown: stop the watcher (await it so a mid-flight snapshot finishes
    # releasing its lock), close DB connections, then take a final snapshot
    # (best effort -- captures anything the watcher hadn't pushed yet).
    if watcher_task is not None:
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()
    if backup_svc.enabled() and backup_svc.dirty():
        try:
            await backup_svc.backup()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Final shutdown backup failed: %s", exc)
    logger.info("BidOps AI shutdown complete")


settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

register_exception_handlers(app)

# CORS (local dev: allow all). Added first => innermost of the custom stack.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (off by default; safety valve for the free-tier LLM keys).
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    per_minute=settings.rate_limit_per_minute,
    burst=settings.rate_limit_burst,
)

# Observability OUTERMOST: assigns the request id (so RateLimit's 429 can carry
# it), injects security + correlation headers, logs one line per request. DO NOT
# reorder these three add_middleware calls.
app.add_middleware(ObservabilityMiddleware)

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
app.include_router(offers_router, prefix="/api")
app.include_router(pricing_router, prefix="/api")
app.include_router(indirects_router, prefix="/api")
app.include_router(historical_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(deliverables_router, prefix="/api")
app.include_router(versioning_router, prefix="/api")
app.include_router(backup_router, prefix="/api")

# Include page routes (imported here to avoid circular import with templates)
from app.api.pages import router as pages_router  # noqa: E402

app.include_router(pages_router)

# Mount static files (MUST be last -- it's a catch-all mount)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
