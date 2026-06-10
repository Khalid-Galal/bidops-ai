# Phase 14 — Deliverables + Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the last-mile outputs: a project status **dashboard** (JSON API + server-rendered page), **indirects client-template population** (the cap-10 gap — fill the client's indirects Excel, formula-preserving), and a **deliverables assembler** that bundles every client-ready artifact (pricing summary, gaps report, per-package comparison matrices, packages register, briefs, manifest) into one folder with a zip download.

**Architecture:** Pure logic + openpyxl — no LLM. `DashboardService` aggregates counts via explicit grouped queries (no lazy loads) and reuses `PricingService` for the money headline. The indirects template writer mirrors the Phase 11 `template_writer` discipline exactly: `pick_sheet` (shared helper), alias-based column detection with explicit override, fuzzy label matching via the Phase 11 matcher (underscores normalized to spaces), **never overwrite a formula cell**, and the hardened upload endpoint pattern (.xlsx-only, size cap, broad-except → 400, temp cleanup). `DeliverablesService` (output-root injectable, like `PackageExporter`) rebuilds idempotently and the download endpoint zips via `shutil.make_archive` to a unique temp path with `BackgroundTask` cleanup. One Jinja page (`dashboard.html` extending `base.html`) makes the v2 backend visible in the existing v1 UI.

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + aiosqlite · openpyxl · Jinja2 (existing `templates` engine) · stdlib `shutil`/`zipfile` · pytest-asyncio + httpx ASGITransport.

**No database migration is required** — everything is computed from existing tables.

---

## Pre-flight (read, do not skip)

1. **No lazy loads in async paths.** Dashboard counts come from explicit `select(Model.status, func.count()).group_by(...)` queries; never touch a relationship attribute.
2. **Underscore matching pitfall:** `match_score` keeps `site_supervision` as ONE token (underscore is `\w`), so it scores poorly against the label "Site Supervision". Always `name.replace("_", " ")` before matching component names against template labels.
3. **Formula preservation discipline (Phase 11 lesson):** load the template workbook with openpyxl defaults (NOT `read_only`, NOT `data_only`), and skip any target cell whose value is a `str` starting with `"="` (count it as `skipped_formula`).
4. **Upload hardening (recurring Phases 9–11 lesson):** the indirects-template endpoint must validate `.xlsx` BEFORE writing a temp file, stream in 1 MB chunks against `_MAX_UPLOAD_BYTES` → 413, catch `(ValueError, BadZipFile, InvalidFileException, KeyError)` → 400, and unlink temp files in `finally`. Copy the structure of `app/api/pricing.py::populate_client_template` exactly.
5. **Reuse, don't re-derive:** direct cost / money figures come from `PricingService.pricing_summary` + `IndirectsService.project_cost_summary` / `compute`; comparison workbooks from `app/services/offer/comparison_export.export_comparison_excel(comparison_dict, path)`; the register path from `PackageExporter().register_path(project_id)`; sheet choice from `app.services.boq.sheet_select.pick_sheet`.
6. **The Jinja engine** lives in `app/main.py` (`templates`); page routes import it as `from app.main import templates` (see `app/api/pages.py`). `base.html` exposes `{% block title %}` and `{% block content %}`. Page routes have NO `/api` prefix; `/projects/{id}/dashboard` does not collide with the existing `/projects/{id}` page route (different segment count).
7. **Services take `db: AsyncSession`;** `DeliverablesService(output_root=...)` is injectable for tests (mirror `PackageExporter`); API tests monkeypatch the router's service class like `tests/packaging/test_packaging_api.py` does.

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (must stay green; baseline = **220 passing**).

---

## File Structure

**Create:**
- `app/schemas/dashboard.py` — dashboard response model.
- `app/services/dashboard/__init__.py`, `app/services/dashboard/dashboard_service.py` — `DashboardService.project_dashboard`.
- `app/api/dashboard.py` — `GET /api/projects/{id}/dashboard`.
- `app/templates/dashboard.html` — server-rendered dashboard page.
- `app/services/indirects/indirects_template.py` — `populate_indirects_template` + `detect_columns`.
- `app/services/deliverables/__init__.py`, `app/services/deliverables/deliverables_service.py` — `DeliverablesService`.
- `app/api/deliverables.py` — build + download endpoints.
- `tests/dashboard/__init__.py`, `tests/dashboard/test_dashboard_service.py`, `tests/dashboard/test_dashboard_api.py`, `tests/dashboard/test_dashboard_page.py`
- `tests/deliverables/__init__.py`, `tests/deliverables/test_indirects_template.py`, `tests/deliverables/test_deliverables_service.py`, `tests/deliverables/test_deliverables_api.py`

**Modify:**
- `app/api/pages.py` — add the dashboard page route.
- `app/api/indirects.py` — add `POST /projects/{id}/indirects/populate-template`.
- `app/main.py` — register `dashboard_router` + `deliverables_router`.

---

## Task 1: DashboardService + schema

**Files:**
- Create: `app/schemas/dashboard.py`, `app/services/dashboard/__init__.py`, `app/services/dashboard/dashboard_service.py`
- Test: `tests/dashboard/__init__.py`, `tests/dashboard/test_dashboard_service.py`

- [ ] **Step 1: Write the schema**

Create `app/schemas/dashboard.py`:

```python
"""Schema for the project status dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PackageCard(BaseModel):
    id: int
    code: str
    name: str
    trade_category: str
    status: str
    total_items: int
    offers_received: int
    offers_evaluated: int


class ProjectDashboard(BaseModel):
    project: dict
    documents: dict
    boq: dict
    packages: list[PackageCard] = Field(default_factory=list)
    package_status_counts: dict[str, int] = Field(default_factory=dict)
    suppliers: dict
    offers: dict
    emails: dict
    pricing: dict
    gaps: dict
    historical: dict
```

- [ ] **Step 2: Write the failing tests**

Create `tests/dashboard/__init__.py` (empty file).

Create `tests/dashboard/test_dashboard_service.py`:

```python
import pytest

from app.models.base import EmailStatus, EmailType, OfferStatus
from app.models.boq import BOQItem
from app.models.document import Document
from app.models.email import EmailLog
from app.models.historical import HistoricalPrice
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.dashboard.dashboard_service import DashboardService


async def _seed_full(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    db.add_all([
        Document(project_id=project.id, filename="a.pdf", file_path="/t/a.pdf",
                 file_type="pdf", file_size=1, status="completed"),
        Document(project_id=project.id, filename="b.pdf", file_path="/t/b.pdf",
                 file_type="pdf", file_size=1, status="failed"),
    ])
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                      trade_category="mep", total_items=2, offers_received=2,
                      offers_evaluated=1)
    db.add(package)
    supplier = Supplier(name="CoolAir", emails=["s@x.test"], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    db.add_all([
        BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                description="AC", unit="no", quantity=5, client_row_index=2,
                trade_category="mep", unit_rate=1200, total_price=6000, currency="USD"),
        BOQItem(project_id=project.id, package_id=package.id, line_number="2",
                description="VRF", unit="no", quantity=2, client_row_index=3,
                trade_category="mep"),  # unpriced
        BOQItem(project_id=project.id, line_number="3", description="Excl", unit="no",
                quantity=1, client_row_index=4, unit_rate=9, total_price=9,
                is_excluded=True),
    ])
    db.add_all([
        SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.EVALUATED.value, file_paths=[], total_price=6000),
        SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.RECEIVED.value, file_paths=[]),
    ])
    db.add(EmailLog(package_id=package.id, supplier_id=supplier.id,
                    email_type=EmailType.RFQ.value, status=EmailStatus.DRAFT.value,
                    to=["s@x.test"], subject="RFQ", body_html="<p>x</p>"))
    db.add(HistoricalPrice(description="AC unit", rate=1000.0, source="import:x"))
    await db.commit()
    return project.id


async def test_dashboard_aggregates_counts(db_session):
    pid = await _seed_full(db_session)
    out = await DashboardService().project_dashboard(db_session, pid)
    assert out["project"]["name"] == "Metro"
    assert out["documents"] == {"total": 2, "by_status": {"completed": 1, "failed": 1}}
    assert out["boq"]["total"] == 3
    assert out["boq"]["priced"] == 1  # excluded one doesn't count
    assert out["boq"]["unpriced"] == 1
    assert out["boq"]["excluded"] == 1
    assert len(out["packages"]) == 1
    assert out["packages"][0]["code"] == "PKG-001-MEP"
    assert out["package_status_counts"] == {"draft": 1}
    assert out["offers"]["total"] == 2
    assert out["offers"]["by_status"] == {"evaluated": 1, "received": 1}
    assert out["emails"]["total"] == 1
    assert out["emails"]["by_type"] == {"rfq": 1}
    assert out["suppliers"]["total"] == 1
    assert out["pricing"]["cost_subtotal"] == 6000.0
    assert out["gaps"]["unpriced"] == 1
    assert out["historical"]["corpus_records"] == 1


async def test_dashboard_empty_project(db_session):
    project = Project(name="Empty")
    db_session.add(project)
    await db_session.commit()
    out = await DashboardService().project_dashboard(db_session, project.id)
    assert out["documents"]["total"] == 0
    assert out["boq"]["total"] == 0
    assert out["packages"] == []
    assert out["offers"]["total"] == 0
    assert out["pricing"]["cost_subtotal"] == 0.0


async def test_dashboard_unknown_project(db_session):
    with pytest.raises(ValueError):
        await DashboardService().project_dashboard(db_session, 999999)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/dashboard/test_dashboard_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.dashboard`.

- [ ] **Step 4: Implement the service**

Create `app/services/dashboard/__init__.py` (empty file).

Create `app/services/dashboard/dashboard_service.py`:

```python
"""Aggregated project status for the dashboard. Explicit queries only —
no relationship lazy-loads (MissingGreenlet), no LLM."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.document import Document
from app.models.email import EmailLog
from app.models.historical import HistoricalPrice
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.pricing.pricing_service import PricingService


class DashboardService:
    async def project_dashboard(self, db: AsyncSession, project_id: int) -> dict:
        project = await db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        docs_by_status = dict(
            (
                await db.execute(
                    select(Document.status, func.count())
                    .where(Document.project_id == project_id)
                    .group_by(Document.status)
                )
            ).all()
        )

        boq_total = (
            await db.execute(
                select(func.count(BOQItem.id)).where(BOQItem.project_id == project_id)
            )
        ).scalar() or 0
        boq_priced = (
            await db.execute(
                select(func.count(BOQItem.id)).where(
                    BOQItem.project_id == project_id,
                    BOQItem.unit_rate.is_not(None),
                    BOQItem.is_excluded.is_(False),
                )
            )
        ).scalar() or 0
        boq_excluded = (
            await db.execute(
                select(func.count(BOQItem.id)).where(
                    BOQItem.project_id == project_id, BOQItem.is_excluded.is_(True)
                )
            )
        ).scalar() or 0
        boq_classified = (
            await db.execute(
                select(func.count(BOQItem.id)).where(
                    BOQItem.project_id == project_id,
                    BOQItem.trade_category.is_not(None),
                )
            )
        ).scalar() or 0

        packages = list(
            (
                await db.execute(
                    select(Package)
                    .where(Package.project_id == project_id)
                    .order_by(Package.code)
                )
            ).scalars().all()
        )
        package_ids = [p.id for p in packages]
        package_status_counts = dict(Counter(p.status for p in packages))

        offers_by_status: dict[str, int] = {}
        emails_by_status: dict[str, int] = {}
        emails_by_type: dict[str, int] = {}
        if package_ids:
            offers_by_status = dict(
                (
                    await db.execute(
                        select(SupplierOffer.status, func.count())
                        .where(SupplierOffer.package_id.in_(package_ids))
                        .group_by(SupplierOffer.status)
                    )
                ).all()
            )
            emails_by_status = dict(
                (
                    await db.execute(
                        select(EmailLog.status, func.count())
                        .where(EmailLog.package_id.in_(package_ids))
                        .group_by(EmailLog.status)
                    )
                ).all()
            )
            emails_by_type = dict(
                (
                    await db.execute(
                        select(EmailLog.email_type, func.count())
                        .where(EmailLog.package_id.in_(package_ids))
                        .group_by(EmailLog.email_type)
                    )
                ).all()
            )

        suppliers_total = (
            await db.execute(select(func.count(Supplier.id)))
        ).scalar() or 0
        suppliers_active = (
            await db.execute(
                select(func.count(Supplier.id)).where(Supplier.is_active.is_(True))
            )
        ).scalar() or 0

        pricing_svc = PricingService()
        pricing = await pricing_svc.pricing_summary(db, project_id)
        gaps = await pricing_svc.gaps_report(db, project_id)

        historical_count = (
            await db.execute(select(func.count(HistoricalPrice.id)))
        ).scalar() or 0

        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "extraction_status": project.extraction_status,
                "checklist_status": project.checklist_status,
            },
            "documents": {
                "total": sum(docs_by_status.values()),
                "by_status": docs_by_status,
            },
            "boq": {
                "total": boq_total,
                "classified": boq_classified,
                "priced": boq_priced,
                "unpriced": boq_total - boq_priced - boq_excluded,
                "excluded": boq_excluded,
            },
            "packages": [
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "trade_category": p.trade_category,
                    "status": p.status,
                    "total_items": p.total_items or 0,
                    "offers_received": p.offers_received or 0,
                    "offers_evaluated": p.offers_evaluated or 0,
                }
                for p in packages
            ],
            "package_status_counts": package_status_counts,
            "suppliers": {"total": suppliers_total, "active": suppliers_active},
            "offers": {
                "total": sum(offers_by_status.values()),
                "by_status": offers_by_status,
            },
            "emails": {
                "total": sum(emails_by_status.values()),
                "by_status": emails_by_status,
                "by_type": emails_by_type,
            },
            "pricing": {
                "cost_subtotal": pricing["cost_subtotal"],
                "grand_total": pricing["grand_total"],
                "currency": pricing["currency"],
                "completion_rate": pricing["completion_rate"],
                "priced_items": pricing["priced_items"],
                "unpriced_items": pricing["unpriced_items"],
            },
            "gaps": {
                "unpriced": gaps["unpriced_count"],
                "needs_review": gaps["needs_review_count"],
                "excluded": gaps["excluded_count"],
            },
            "historical": {"corpus_records": historical_count},
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/dashboard/test_dashboard_service.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/dashboard.py app/services/dashboard/ tests/dashboard/__init__.py tests/dashboard/test_dashboard_service.py
git commit -m "feat(phase-14): DashboardService — aggregated project status"
```

---

## Task 2: Dashboard API endpoint + Jinja page

**Files:**
- Create: `app/api/dashboard.py`, `app/templates/dashboard.html`
- Modify: `app/main.py`, `app/api/pages.py`
- Test: `tests/dashboard/test_dashboard_api.py`, `tests/dashboard/test_dashboard_page.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/dashboard/test_dashboard_api.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def dash_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro Dashboard")
        seed.add(project)
        await seed.commit()
        pid = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, pid
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_dashboard_endpoint(dash_client):
    client, pid = dash_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["project"]["name"] == "Metro Dashboard"
        assert body["documents"]["total"] == 0
        assert body["packages"] == []


async def test_dashboard_404(dash_client):
    client, _ = dash_client
    async with client as c:
        r = await c.get("/api/projects/999999/dashboard")
    assert r.status_code == 404
```

Create `tests/dashboard/test_dashboard_page.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def page_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro Page")
        seed.add(project)
        await seed.commit()
        pid = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, pid
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_dashboard_page_renders(page_client):
    client, pid = page_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/dashboard")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Metro Page" in r.text
        assert "Dashboard" in r.text


async def test_dashboard_page_404(page_client):
    client, _ = page_client
    async with client as c:
        r = await c.get("/projects/999999/dashboard")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/dashboard/test_dashboard_api.py tests/dashboard/test_dashboard_page.py -q`
Expected: FAIL — 404s (routes not registered).

- [ ] **Step 3: Implement the API router**

Create `app/api/dashboard.py`:

```python
"""Dashboard API: aggregated project status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.dashboard import ProjectDashboard
from app.services.dashboard.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/dashboard", response_model=ProjectDashboard)
async def project_dashboard(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> ProjectDashboard:
    try:
        data = await DashboardService().project_dashboard(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectDashboard(**data)
```

- [ ] **Step 4: Add the page route to `app/api/pages.py`**

Append to `app/api/pages.py`:

```python
@router.get("/projects/{project_id}/dashboard")
async def dashboard_page(
    request: Request,
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Render the project status dashboard page."""
    from app.services.dashboard.dashboard_service import DashboardService

    try:
        data = await DashboardService().project_dashboard(db, project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "d": data},
    )
```

(The module already imports `Request`, `HTTPException`, `status`, `templates`, `Depends`, `AsyncSession`, `get_db`.)

- [ ] **Step 5: Create the template**

Create `app/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}{{ d.project.name }} — Dashboard | BidOps AI{% endblock %}
{% block content %}
<h1>Dashboard — {{ d.project.name }}</h1>
<p>
  Status: <strong>{{ d.project.status }}</strong>
  {% if d.project.extraction_status %} · Extraction: {{ d.project.extraction_status }}{% endif %}
  {% if d.project.checklist_status %} · Checklist: {{ d.project.checklist_status }}{% endif %}
</p>

<h2>Pricing</h2>
<table border="1" cellpadding="6">
  <tr><th>Direct cost</th><th>Grand total</th><th>Currency</th><th>Completion</th><th>Priced</th><th>Unpriced</th></tr>
  <tr>
    <td>{{ d.pricing.cost_subtotal }}</td>
    <td>{{ d.pricing.grand_total }}</td>
    <td>{{ d.pricing.currency }}</td>
    <td>{{ d.pricing.completion_rate }}%</td>
    <td>{{ d.pricing.priced_items }}</td>
    <td>{{ d.pricing.unpriced_items }}</td>
  </tr>
</table>

<h2>Counts</h2>
<table border="1" cellpadding="6">
  <tr><th>Documents</th><th>BOQ items</th><th>BOQ priced</th><th>Packages</th><th>Offers</th><th>Emails</th><th>Suppliers</th><th>Historical records</th></tr>
  <tr>
    <td>{{ d.documents.total }}</td>
    <td>{{ d.boq.total }}</td>
    <td>{{ d.boq.priced }}</td>
    <td>{{ d.packages | length }}</td>
    <td>{{ d.offers.total }}</td>
    <td>{{ d.emails.total }}</td>
    <td>{{ d.suppliers.total }}</td>
    <td>{{ d.historical.corpus_records }}</td>
  </tr>
</table>

<h2>Packages</h2>
{% if d.packages %}
<table border="1" cellpadding="6">
  <tr><th>Code</th><th>Name</th><th>Trade</th><th>Status</th><th>Items</th><th>Offers</th><th>Evaluated</th></tr>
  {% for p in d.packages %}
  <tr>
    <td>{{ p.code }}</td><td>{{ p.name }}</td><td>{{ p.trade_category }}</td>
    <td>{{ p.status }}</td><td>{{ p.total_items }}</td>
    <td>{{ p.offers_received }}</td><td>{{ p.offers_evaluated }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}<p>No packages yet.</p>{% endif %}

<h2>Gaps</h2>
<p>Unpriced: {{ d.gaps.unpriced }} · Needs review: {{ d.gaps.needs_review }} · Excluded: {{ d.gaps.excluded }}</p>
{% endblock %}
```

- [ ] **Step 6: Register the API router in `app/main.py`**

Add the import (alphabetical block is fine):

```python
from app.api.dashboard import router as dashboard_router
```

Add the registration after the historical router:

```python
app.include_router(dashboard_router, prefix="/api")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/dashboard/ -q`
Expected: PASS (7 tests).

- [ ] **Step 8: Commit**

```bash
git add app/api/dashboard.py app/api/pages.py app/templates/dashboard.html app/main.py tests/dashboard/test_dashboard_api.py tests/dashboard/test_dashboard_page.py
git commit -m "feat(phase-14): dashboard API endpoint + server-rendered dashboard page"
```

---

## Task 3: Indirects client-template population

**Files:**
- Create: `app/services/indirects/indirects_template.py`
- Modify: `app/api/indirects.py`
- Test: `tests/deliverables/__init__.py`, `tests/deliverables/test_indirects_template.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/deliverables/__init__.py` (empty file).

Create `tests/deliverables/test_indirects_template.py`:

```python
import openpyxl
import pytest

from app.services.indirects.indirects_template import (
    detect_columns,
    populate_indirects_template,
)


def _make_template(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Indirects"
    ws.append(["Item", "Description", "Amount"])           # row 1 header
    ws.append([1, "Site Supervision", None])               # row 2
    ws.append([2, "Temporary Works", None])                # row 3
    ws.append([3, "Project Manager", None])                # row 4
    ws.append([4, "Total Indirects", "=SUM(C2:C4)"])       # row 5 formula
    wb.save(path)
    return str(path)


def test_detect_columns():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Amount"])
    label_col, amount_col = detect_columns(ws)
    assert amount_col == 3
    assert label_col == 2


def test_populate_matches_labels_and_preserves_formula(tmp_path):
    src = _make_template(tmp_path / "ind.xlsx")
    out = str(tmp_path / "out.xlsx")
    components = {
        "site_supervision": 660.0,
        "temporary_works": 440.0,
        "project_manager": 30000.0,
        "total_indirects": 31100.0,  # the Total row holds a formula -> skipped
    }
    result = populate_indirects_template(src, out, components)
    assert result["written"] == 3
    assert result["skipped_formula"] == 1
    assert result["unmatched_components"] == []
    wb = openpyxl.load_workbook(out)
    ws = wb["Indirects"]
    assert ws.cell(row=2, column=3).value == 660.0
    assert ws.cell(row=3, column=3).value == 440.0
    assert ws.cell(row=4, column=3).value == 30000.0
    assert ws.cell(row=5, column=3).value == "=SUM(C2:C4)"  # formula intact


def test_populate_reports_unmatched(tmp_path):
    src = _make_template(tmp_path / "i.xlsx")
    out = str(tmp_path / "o.xlsx")
    result = populate_indirects_template(src, out, {"helicopter_rental": 5.0})
    assert result["written"] == 0
    assert result["unmatched_components"] == ["helicopter_rental"]


def test_populate_explicit_columns(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Site Supervision", None])   # no header row at all
    p = tmp_path / "nohdr.xlsx"
    wb.save(p)
    result = populate_indirects_template(
        str(p), str(tmp_path / "o2.xlsx"), {"site_supervision": 99.0},
        amount_column=2, label_column=1,
    )
    assert result["written"] == 1


def test_populate_raises_without_amount_column(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Just", "Words"])
    p = tmp_path / "bad.xlsx"
    wb.save(p)
    with pytest.raises(ValueError):
        populate_indirects_template(str(p), str(tmp_path / "o3.xlsx"), {"x": 1.0})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/deliverables/test_indirects_template.py -q`
Expected: FAIL — `ModuleNotFoundError: ...indirects_template`.

- [ ] **Step 3: Implement the template writer**

Create `app/services/indirects/indirects_template.py`:

```python
"""Fill a client's indirects Excel template, formula-preserving.

Rows are matched by fuzzy label similarity (Phase 11 matcher; component names
have underscores normalized to spaces). Only the detected amount column is
written; any target cell holding a formula string is skipped. Loaded with
openpyxl defaults so formulas elsewhere survive (pivot tables / VBA are not
round-tripped — .xlsm is rejected at the API layer)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from app.services.boq.sheet_select import pick_sheet
from app.services.pricing.line_item_matcher import match_score

# Priority-ordered: the FIRST alias found wins, so "description" beats "item"
# (an "Item" number column must not be mistaken for the label column) and
# "amount" beats "total" (a row-sum "Total" column must not be the write target).
_AMOUNT_ALIASES = ("amount", "value", "cost", "price", "total", "rate")
_LABEL_ALIASES = (
    "description", "particulars", "indirect item", "indirects", "indirect",
    "component", "item",
)
_MAX_HEADER_SCAN = 20
_MATCH_THRESHOLD = 0.45


def _norm(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def detect_columns(ws) -> tuple[int | None, int | None]:
    """Return (label_col, amount_col) from the first header row that names an
    amount-like column. Aliases are matched in PRIORITY order (not column
    order); label falls back to column 1."""
    for r in range(1, min(ws.max_row, _MAX_HEADER_SCAN) + 1):
        headers: dict[str, int] = {}
        for c in range(1, ws.max_column + 1):
            cell = _norm(ws.cell(row=r, column=c).value)
            if cell and cell not in headers:
                headers[cell] = c
        amount_col = next((headers[a] for a in _AMOUNT_ALIASES if a in headers), None)
        if amount_col is not None:
            label_col = next((headers[a] for a in _LABEL_ALIASES if a in headers), None)
            return (label_col or 1), amount_col
    return None, None


def populate_indirects_template(
    template_path: str,
    output_path: str,
    components: dict[str, float],
    *,
    amount_column: int | None = None,
    label_column: int | None = None,
) -> dict:
    """Write each component amount next to its best-matching row label.

    Each component is written at most once (best-scoring unused component per
    row, rows scanned top-down). Formula cells are never overwritten.
    Raises ValueError if no amount column can be determined.
    """
    wb = load_workbook(template_path)  # defaults preserve formulas
    try:
        ws = pick_sheet(wb)
        det_label, det_amount = detect_columns(ws)
        label_col = label_column or det_label or 1
        amount_col = amount_column or det_amount
        if amount_col is None:
            raise ValueError(
                "Could not detect an amount column in the template; "
                "pass amount_column explicitly"
            )

        remaining = dict(components)
        written = skipped_formula = 0
        for r in range(1, ws.max_row + 1):
            if not remaining:
                break
            label = ws.cell(row=r, column=label_col).value
            if label is None or str(label).strip() == "":
                continue
            label_text = str(label)
            best_name: str | None = None
            best_score = 0.0
            for name in remaining:
                # underscores are word chars to the matcher: normalize to spaces
                score = match_score(label_text, name.replace("_", " "))
                if score > best_score:
                    best_name, best_score = name, score
            if best_name is None or best_score < _MATCH_THRESHOLD:
                continue
            target = ws.cell(row=r, column=amount_col)
            if isinstance(target.value, str) and target.value.startswith("="):
                skipped_formula += 1
                remaining.pop(best_name)  # row exists but is formula-driven
                continue
            target.value = round(remaining.pop(best_name), 2)
            written += 1

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return {
            "written": written,
            "skipped_formula": skipped_formula,
            "amount_column": amount_col,
            "label_column": label_col,
            "unmatched_components": sorted(remaining),
        }
    finally:
        wb.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/deliverables/test_indirects_template.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Add the hardened upload endpoint to `app/api/indirects.py`**

Add these imports at the top of `app/api/indirects.py`:

```python
import tempfile
from pathlib import Path
from zipfile import BadZipFile

from fastapi import File, Form, UploadFile
from fastapi.responses import FileResponse
from openpyxl.utils.exceptions import InvalidFileException
from starlette.background import BackgroundTask

from app.services.indirects.indirects_template import populate_indirects_template
from app.services.pricing.pricing_service import PricingService
```

(Merge with the existing `fastapi` import line rather than duplicating it.)

Add module-level constants after `router = APIRouter(...)`:

```python
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_TEMPLATE_EXT = {".xlsx"}
```

Add the endpoint at the end of the file:

```python
@router.post("/projects/{project_id}/indirects/populate-template")
async def populate_indirects_client_template(
    project_id: int,
    file: UploadFile = File(...),
    amount_column: int | None = Form(default=None),
    label_column: int | None = Form(default=None),
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
):
    """Fill the client's indirects template with computed amounts (formula-
    preserving). Components come from rules.indirects applied to the project's
    priced direct cost."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_TEMPLATE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported template type; upload .xlsx")

    summary = await PricingService().pricing_summary(db, project_id)
    ind = IndirectsService().compute(
        summary["cost_subtotal"], duration_months=duration_months, location=location
    )
    components = {
        **ind["percentage_based"],
        **ind["duration_based"],
        "total_indirects": ind["total_indirects"],
    }
    components = {k: v for k, v in components.items() if v}
    if not components:
        raise HTTPException(
            status_code=409,
            detail="No indirect amounts to populate; price the BOQ or set duration_months.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as src_tmp:
        src_path = src_tmp.name
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                src_tmp.close()
                Path(src_path).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail="Upload exceeds the maximum allowed size"
                )
            src_tmp.write(chunk)
    out_path = src_path + ".populated.xlsx"
    try:
        populate_indirects_template(
            src_path, out_path, components,
            amount_column=amount_column, label_column=label_column,
        )
    except (ValueError, BadZipFile, InvalidFileException, KeyError) as exc:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
        raise

    def _cleanup() -> None:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)

    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"indirects_project_{project_id}.xlsx",
        background=BackgroundTask(_cleanup),
    )
```

- [ ] **Step 6: Write + run the endpoint tests**

Append to `tests/deliverables/test_indirects_template.py`:

```python
import io

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def ind_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.boq import BOQItem
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        seed.add(BOQItem(project_id=project.id, line_number="1", description="AC",
                         unit="no", quantity=5, client_row_index=2, trade_category="mep",
                         unit_rate=1200, total_price=6000, currency="USD"))
        await seed.commit()
        pid = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, pid
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


def _template_bytes():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Indirects"
    ws.append(["Item", "Description", "Amount"])
    ws.append([1, "Site Supervision", None])
    ws.append([2, "Total Indirects", "=SUM(C2:C2)"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def test_populate_template_endpoint(ind_client):
    client, pid = ind_client
    async with client as c:
        r = await c.post(
            f"/api/projects/{pid}/indirects/populate-template",
            files={"file": ("ind.xlsx", _template_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200, r.text
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        ws = wb["Indirects"]
        # site_supervision = 0.03 * 6000 = 180.0 (default rules)
        assert ws.cell(row=2, column=3).value == 180.0
        assert ws.cell(row=3, column=3).value == "=SUM(C2:C2)"  # formula intact


async def test_populate_template_rejects_non_xlsx(ind_client):
    client, pid = ind_client
    async with client as c:
        r = await c.post(
            f"/api/projects/{pid}/indirects/populate-template",
            files={"file": ("x.txt", b"nope", "text/plain")},
        )
    assert r.status_code == 400


async def test_populate_template_404_missing_project(ind_client):
    client, _ = ind_client
    async with client as c:
        r = await c.post(
            "/api/projects/999999/indirects/populate-template",
            files={"file": ("i.xlsx", _template_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 404
```

Run: `.venv/Scripts/python.exe -m pytest tests/deliverables/test_indirects_template.py -q`
Expected: PASS (8 tests).

- [ ] **Step 7: Commit**

```bash
git add app/services/indirects/indirects_template.py app/api/indirects.py tests/deliverables/__init__.py tests/deliverables/test_indirects_template.py
git commit -m "feat(phase-14): indirects client-template population — fuzzy label match, formula-preserving"
```

---

## Task 4: DeliverablesService + build/download endpoints

**Files:**
- Create: `app/services/deliverables/__init__.py`, `app/services/deliverables/deliverables_service.py`, `app/api/deliverables.py`
- Modify: `app/main.py`
- Test: `tests/deliverables/test_deliverables_service.py`, `tests/deliverables/test_deliverables_api.py`

- [ ] **Step 1: Write the failing service tests**

Create `tests/deliverables/test_deliverables_service.py`:

```python
import json
from pathlib import Path

import pytest

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.deliverables.deliverables_service import DeliverablesService


async def _seed(db, tmp_path):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    brief = tmp_path / "brief.html"
    brief.write_text("<h1>Brief</h1>")
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                      trade_category="mep", brief_path=str(brief))
    db.add(package)
    supplier = Supplier(name="CoolAir", emails=[], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    db.add(BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                   description="AC", unit="no", quantity=5, client_row_index=2,
                   trade_category="mep", unit_rate=1200, total_price=6000, currency="USD"))
    db.add(SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                         status=OfferStatus.EVALUATED.value, file_paths=[],
                         total_price=6000, currency="USD", overall_score=75.0, rank=1))
    await db.commit()
    return project.id


async def test_build_assembles_deliverables(db_session, tmp_path):
    pid = await _seed(db_session, tmp_path)
    svc = DeliverablesService(output_root=tmp_path / "deliv")
    result = await svc.build(db_session, pid)
    folder = Path(result["folder"])
    names = set(result["files"])
    assert "Pricing_Summary.xlsx" in names
    assert "Pricing_Gaps.xlsx" in names
    assert "Comparison_PKG-001-MEP.xlsx" in names
    assert "manifest.json" in names
    assert (folder / "Briefs" / "brief.html").exists()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["project_id"] == pid
    assert manifest["project_name"] == "Metro"
    assert "generated_at" in manifest


async def test_build_is_idempotent(db_session, tmp_path):
    pid = await _seed(db_session, tmp_path)
    svc = DeliverablesService(output_root=tmp_path / "deliv")
    first = await svc.build(db_session, pid)
    second = await svc.build(db_session, pid)
    assert sorted(first["files"]) == sorted(second["files"])
    # no leftover duplicates from the first build
    folder = Path(second["folder"])
    assert len(list(folder.rglob("*.xlsx"))) == len(
        [f for f in second["files"] if f.endswith(".xlsx")]
    )


async def test_build_unknown_project(db_session, tmp_path):
    with pytest.raises(ValueError):
        await DeliverablesService(output_root=tmp_path).build(db_session, 999999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/deliverables/test_deliverables_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.deliverables`.

- [ ] **Step 3: Implement the service**

Create `app/services/deliverables/__init__.py` (empty file).

Create `app/services/deliverables/deliverables_service.py`:

```python
"""Assemble the client-ready deliverables bundle for a project.

Collects: Pricing_Summary.xlsx (full cost rollup + by-trade), Pricing_Gaps.xlsx,
one offer-comparison matrix per package with offers, the Packages Register
(if exported), package briefs, and a manifest.json. Rebuilds are idempotent
(the project folder is recreated from scratch). Pure logic — no LLM."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.package import Package
from app.models.project import Project
from app.services.indirects.indirects_service import IndirectsService
from app.services.offer.comparison_export import export_comparison_excel
from app.services.offer.scoring_service import ScoringService
from app.services.packaging.package_exporter import PackageExporter
from app.services.pricing.pricing_service import PricingService

_SAFE = re.compile(r"[^\w\-]+")


def _safe_name(text: str) -> str:
    return _SAFE.sub("_", text).strip("_") or "package"


class DeliverablesService:
    def __init__(self, output_root: Path | str = "data/deliverables") -> None:
        self._root = Path(output_root)

    def project_dir(self, project_id: int) -> Path:
        return self._root / f"project_{project_id}"

    async def build(self, db: AsyncSession, project_id: int) -> dict:
        project = await db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        dest = self.project_dir(project_id)
        if dest.exists():
            shutil.rmtree(dest)  # idempotent rebuild
        dest.mkdir(parents=True)

        files: list[str] = []

        pricing_svc = PricingService()
        pricing = await pricing_svc.pricing_summary(db, project_id)
        cost = await IndirectsService().project_cost_summary(db, project_id)
        self._write_pricing_workbook(cost, pricing, dest / "Pricing_Summary.xlsx")
        files.append("Pricing_Summary.xlsx")

        gaps = await pricing_svc.gaps_report(db, project_id)
        self._write_gaps_workbook(gaps, dest / "Pricing_Gaps.xlsx")
        files.append("Pricing_Gaps.xlsx")

        packages = list(
            (
                await db.execute(
                    select(Package).where(Package.project_id == project_id)
                )
            ).scalars().all()
        )
        comparisons = 0
        scoring = ScoringService()
        for package in packages:
            comparison = await scoring.compare(db, package.id)
            if comparison["total_offers"] == 0:
                continue
            name = f"Comparison_{_safe_name(package.code)}.xlsx"
            export_comparison_excel(comparison, str(dest / name))
            files.append(name)
            comparisons += 1

        register = PackageExporter().register_path(project_id)
        if register.exists():
            shutil.copy2(register, dest / "Packages_Register.xlsx")
            files.append("Packages_Register.xlsx")

        briefs = 0
        briefs_dir = dest / "Briefs"
        for package in packages:
            if package.brief_path and Path(package.brief_path).exists():
                briefs_dir.mkdir(exist_ok=True)
                target = briefs_dir / Path(package.brief_path).name
                shutil.copy2(package.brief_path, target)
                files.append(f"Briefs/{target.name}")
                briefs += 1

        manifest = {
            "project_id": project_id,
            "project_name": project.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "grand_total": cost["grand_total"],
            "currency": cost["currency"],
            "files": sorted(files),
            "comparisons": comparisons,
            "briefs": briefs,
        }
        (dest / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        files.append("manifest.json")

        return {
            "project_id": project_id,
            "folder": str(dest),
            "files": sorted(files),
            "comparisons": comparisons,
            "briefs": briefs,
        }

    @staticmethod
    def _write_pricing_workbook(cost: dict, pricing: dict, path: Path) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "Cost Summary"
        rows = [
            ("Direct Cost", cost["direct_cost"]),
            ("Total Indirects", cost["indirects"]["total_indirects"]),
            ("Cost Base (direct + indirects)", cost["total_cost_base"]),
            ("Overhead", cost["markups"]["overhead"]),
            ("Profit", cost["markups"]["profit"]),
            ("Contingency", cost["markups"]["contingency"]),
            ("Risk", cost["markups"]["risk"]),
            ("Markup Total", cost["markups"]["markup_total"]),
            ("Selling Before VAT", cost["selling_before_vat"]),
            (f"VAT ({cost['vat_rate']:.0%})", cost["vat_amount"]),
            ("GRAND TOTAL", cost["grand_total"]),
            ("Currency", cost["currency"]),
        ]
        for label, value in rows:
            ws.append([label, value])
        ws.column_dimensions["A"].width = 32
        ws.column_dimensions["B"].width = 18

        trade_ws = wb.create_sheet("By Trade")
        trade_ws.append(["Trade", "Items", "Total", "% of Direct"])
        for t in pricing["by_trade"]:
            trade_ws.append([t["trade"], t["count"], t["total"], t["percentage"]])
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)

    @staticmethod
    def _write_gaps_workbook(gaps: dict, path: Path) -> None:
        wb = Workbook()
        first = True
        for title, key in (
            ("Unpriced", "unpriced"),
            ("Needs Review", "needs_review"),
            ("Excluded", "excluded"),
        ):
            ws = wb.active if first else wb.create_sheet()
            ws.title = title
            first = False
            ws.append(["ID", "Line", "Description", "Trade", "Reason"])
            for g in gaps[key]:
                ws.append([
                    g["id"], g["line_number"], g["description"],
                    g["trade_category"], g["reason"],
                ])
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/deliverables/test_deliverables_service.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing API tests**

Create `tests/deliverables/test_deliverables_api.py`:

```python
import io
import zipfile

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def deliv_client(tmp_path, monkeypatch):
    import app.api.deliverables as deliv_api
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.boq import BOQItem
    from app.models.project import Project
    from app.services.deliverables.deliverables_service import DeliverablesService

    monkeypatch.setattr(
        deliv_api, "DeliverablesService",
        lambda: DeliverablesService(output_root=tmp_path / "deliv"),
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        seed.add(BOQItem(project_id=project.id, line_number="1", description="AC",
                         unit="no", quantity=5, client_row_index=2, trade_category="mep",
                         unit_rate=1200, total_price=6000, currency="USD"))
        await seed.commit()
        pid = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, pid
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_build_then_download_zip(deliv_client):
    client, pid = deliv_client
    async with client as c:
        b = await c.post(f"/api/projects/{pid}/deliverables/build")
        assert b.status_code == 200, b.text
        assert "Pricing_Summary.xlsx" in b.json()["files"]

        d = await c.get(f"/api/projects/{pid}/deliverables/download")
        assert d.status_code == 200
        assert d.headers["content-type"].startswith("application/zip")
        zf = zipfile.ZipFile(io.BytesIO(d.content))
        assert any(n.endswith("Pricing_Summary.xlsx") for n in zf.namelist())
        assert any(n.endswith("manifest.json") for n in zf.namelist())


async def test_download_404_before_build(deliv_client):
    client, pid = deliv_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/deliverables/download")
    assert r.status_code == 404


async def test_build_404_missing_project(deliv_client):
    client, _ = deliv_client
    async with client as c:
        r = await c.post("/api/projects/999999/deliverables/build")
    assert r.status_code == 404
```

- [ ] **Step 6: Implement the router**

Create `app/api/deliverables.py`:

```python
"""Deliverables API: assemble and download the client-ready submission bundle."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.services.deliverables.deliverables_service import DeliverablesService

router = APIRouter(tags=["deliverables"])


@router.post("/projects/{project_id}/deliverables/build")
async def build_deliverables(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await DeliverablesService().build(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/deliverables/download")
async def download_deliverables(project_id: int):
    folder = DeliverablesService().project_dir(project_id)
    if not folder.is_dir() or not any(folder.iterdir()):
        raise HTTPException(
            status_code=404,
            detail="Deliverables not built — run POST .../deliverables/build first.",
        )
    # Unique temp base per request so concurrent downloads cannot collide.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="")
    base = tmp.name
    tmp.close()
    Path(base).unlink(missing_ok=True)
    zip_path = shutil.make_archive(base, "zip", root_dir=str(folder))
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"deliverables_project_{project_id}.zip",
        background=BackgroundTask(lambda: Path(zip_path).unlink(missing_ok=True)),
    )
```

- [ ] **Step 7: Register the router in `app/main.py`**

Add the import:

```python
from app.api.deliverables import router as deliverables_router
```

Add the registration after the dashboard router:

```python
app.include_router(deliverables_router, prefix="/api")
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/deliverables/ -q`
Expected: PASS (14 tests across the three files).

- [ ] **Step 9: Commit**

```bash
git add app/services/deliverables/ app/api/deliverables.py app/main.py tests/deliverables/test_deliverables_service.py tests/deliverables/test_deliverables_api.py
git commit -m "feat(phase-14): deliverables assembler + zip download endpoints"
```

---

## Task 5: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, zero failures, no new skips. Baseline was 220; this phase adds 3 (dashboard svc) + 2 (dashboard api) + 2 (page) + 8 (indirects template incl. endpoint) + 3 (deliverables svc) + 3 (deliverables api) = **21** → **~241 passing** (±a couple). Hard requirement: zero failures.

- [ ] **Step 2: Smoke-check routes register**

Run:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'dashboard' in p or 'deliverables' in p or 'populate-template' in p))"
```
Expected to include:
```
/api/projects/{project_id}/dashboard
/api/projects/{project_id}/deliverables/build
/api/projects/{project_id}/deliverables/download
/api/projects/{project_id}/indirects/populate-template
/api/projects/{project_id}/pricing/populate-template
/projects/{project_id}/dashboard
```

- [ ] **Step 3: Final commit (if anything uncommitted)**

```bash
git add -A
git commit -m "test(phase-14): full suite green — deliverables + dashboard"
```

---

## Spec Coverage Self-Review

| Phase 14 / plan.md requirement | Task |
|---|---|
| Dashboard for packages, suppliers, offers, status (NFR "UI: Dashboard") | 1, 2 |
| Package all deliverables for submission (cap 12) | 4 |
| Client-ready pricing outputs bundled (cap 12) | 4 (Pricing_Summary + Gaps + comparisons + register + briefs + manifest) |
| Indirects template population (cap 10 gap) | 3 |
| Formula preservation + upload hardening (house rules) | 3 |
| Idempotent rebuild / reproducible outputs (plan.md behavior rules) | 4 |
| Root conventions (db param, injectable output_root, no lazy loads, no migration) | all |

**Deferred / out of scope:** DOCX/PDF narrative export of the project summary (v1 already exports summary/checklist to Excel and degraded-PDF; a styled DOCX is cosmetic); auto-emailing the deliverables bundle; the React SPA (6C — next); auth (15). The dashboard page is intentionally minimal server-rendered HTML — the full UI pass is Phase 6C's job.
