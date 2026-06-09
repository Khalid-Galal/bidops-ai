# Phase 12 — Indirects Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable indirect-cost engine that computes project indirects (percentage-of-direct components, duration-based staff costs, and a location factor) from `rules.indirects`, and a full project cost rollup (direct → + indirects → + markups → + VAT → grand total) that builds on the Phase 11 pricing.

**Architecture:** Pure logic, rules-driven, no LLM and no new DB columns. `IndirectsService` (rules-injectable) reads the project's direct cost from the existing `PricingService.pricing_summary` (`cost_subtotal`, which already excludes excluded items), computes the indirects breakdown from `rules.indirects`, and rolls everything up. To avoid duplicating the markup/VAT formula (a recurring DRY finding in prior phases), the markup+VAT math is extracted once into a shared `compute_commercial(base, rules)` helper that both `pricing_summary` (base = direct cost) and the indirects cost-summary (base = direct + indirects) call. Duration (months) and location are **request inputs** (query params), not stored on the project, so no migration is needed. Root conventions hold: services take `db: AsyncSession`; `RulesService` is injectable (default `RulesService()`); responses are built from explicit queries.

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + aiosqlite · pure-Python arithmetic over the typed `RulesConfig` · pytest-asyncio + httpx ASGITransport.

**No database migration is required** — indirects are computed on the fly from `rules.indirects` and the already-priced BOQ items; duration/location are request parameters.

---

## Pre-flight (read, do not skip)

1. **`rules.indirects` shape** (`app/schemas/rules.py`): `percentage_based: dict[str, float]` (each value a fraction of direct cost, e.g. `site_supervision: 0.03`), `duration_based: dict[str, DurationBasedRole]` where `DurationBasedRole.monthly_rate: float = 0.0`, and `location_factors: dict[str, float]` (default `{"default": 1.0, "remote": 1.15}`). The committed `config/rules.default.json` populates `percentage_based` with 5 components summing to 0.085 and `duration_based` monthly rates of 0.0.
2. **A bare `RulesConfig()` has EMPTY `percentage_based`/`duration_based`** (their schema defaults are empty dicts; the real values live in `config/rules.default.json`). So tests that want the real default percentages must use the real `RulesService()` (which loads the JSON); tests that inject a fake `RulesConfig()` must set the dicts explicitly.
3. **Direct cost comes from `PricingService.pricing_summary(...)["cost_subtotal"]`** — it already sums `total_price` over non-excluded, priced items and resolves the cost `currency`. Reuse it; do not re-sum BOQ items. Pass the same `rules_service` into `PricingService` so an injected fake rules flows through.
4. **Markup base for the cost-summary is `direct + indirects`** (the contractor model: indirects/preliminaries are part of cost, and markup/profit apply on top of total cost). Phase 11's `pricing_summary` keeps applying markup on the direct cost only (its existing, tested "direct-cost view"); the new `cost-summary` is the complete "with-indirects" view. Document this distinction.
5. **`DurationBasedRole` is a Pydantic model** — read the rate via `cfg.monthly_rate` (not `cfg["monthly_rate"]`).
6. **Location factor lookup must be total**: `factors.get(location, factors.get("default", 1.0))` — fall back to the `default` factor, then `1.0`, so an unknown location never crashes.

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (must stay green; baseline = **182 passing**).

---

## File Structure

**Create:**
- `app/services/pricing/commercial.py` — `compute_commercial(base, rules)` shared markup+VAT helper.
- `app/schemas/indirects.py` — indirects + cost-summary response models.
- `app/services/indirects/__init__.py`
- `app/services/indirects/indirects_service.py` — `IndirectsService` (compute, indirects_result, project_cost_summary).
- `app/api/indirects.py` — indirects + cost-summary endpoints.
- `tests/indirects/__init__.py`, `tests/indirects/test_commercial.py`, `tests/indirects/test_indirects_service.py`, `tests/indirects/test_indirects_api.py`

**Modify:**
- `app/services/pricing/pricing_service.py` — `pricing_summary` uses `compute_commercial` (output unchanged; Phase 11 tests must still pass).
- `app/main.py` — register `indirects_router`.

---

## Task 1: Shared `compute_commercial` helper + refactor `pricing_summary`

**Files:**
- Create: `app/services/pricing/commercial.py`
- Modify: `app/services/pricing/pricing_service.py`
- Test: `tests/indirects/__init__.py`, `tests/indirects/test_commercial.py`

- [ ] **Step 1: Write the failing test**

Create `tests/indirects/__init__.py` (empty file).

Create `tests/indirects/test_commercial.py`:

```python
from app.schemas.rules import RulesConfig
from app.services.pricing.commercial import compute_commercial


def test_compute_commercial_default_markups():
    rules = RulesConfig()  # default markup: overhead .08, profit .10, contingency .05, risk .03; vat 0.0
    out = compute_commercial(1000.0, rules)
    assert out["markups"] == {
        "overhead": 80.0, "profit": 100.0, "contingency": 50.0, "risk": 30.0,
        "markup_total": 260.0,
    }
    assert out["selling_before_vat"] == 1260.0
    assert out["vat_rate"] == 0.0
    assert out["vat_amount"] == 0.0
    assert out["grand_total"] == 1260.0


def test_compute_commercial_applies_vat():
    rules = RulesConfig()
    rules.commercial.vat_rate = 0.10
    out = compute_commercial(1000.0, rules)
    assert out["selling_before_vat"] == 1260.0
    assert out["vat_amount"] == 126.0
    assert out["grand_total"] == 1386.0


def test_compute_commercial_zero_base():
    out = compute_commercial(0.0, RulesConfig())
    assert out["markups"]["markup_total"] == 0.0
    assert out["grand_total"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_commercial.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.pricing.commercial`.

- [ ] **Step 3: Implement the helper**

Create `app/services/pricing/commercial.py`:

```python
"""Shared commercial (markup + VAT) computation over a cost base.

Single source of truth for the markup/VAT formula so pricing_summary (base =
direct cost) and the indirects cost-summary (base = direct + indirects) cannot
diverge. All values are configurable via rules.commercial.
"""

from __future__ import annotations


def compute_commercial(base: float, rules) -> dict:
    """Apply rules.commercial markups + VAT to a cost base.

    markup_total = base * sum(overhead, profit, contingency, risk)
    selling_before_vat = base + markup_total
    vat_amount = selling_before_vat * vat_rate
    grand_total = selling_before_vat + vat_amount
    """
    m = rules.commercial.markup
    overhead = round(base * m.overhead, 2)
    profit = round(base * m.profit, 2)
    contingency = round(base * m.contingency, 2)
    risk = round(base * m.risk, 2)
    markup_total = round(overhead + profit + contingency + risk, 2)
    selling_before_vat = round(base + markup_total, 2)
    vat_rate = rules.commercial.vat_rate
    vat_amount = round(selling_before_vat * vat_rate, 2)
    grand_total = round(selling_before_vat + vat_amount, 2)
    return {
        "markups": {
            "overhead": overhead,
            "profit": profit,
            "contingency": contingency,
            "risk": risk,
            "markup_total": markup_total,
        },
        "selling_before_vat": selling_before_vat,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
```

- [ ] **Step 4: Refactor `pricing_summary` to use it**

In `app/services/pricing/pricing_service.py`, add the import near the top (with the other `app.services.pricing` imports):

```python
from app.services.pricing.commercial import compute_commercial
```

Then replace the inline markup/VAT block in `pricing_summary` (the lines computing `m = rules.commercial.markup` through `grand_total = round(selling_before_vat + vat_amount, 2)`) with:

```python
        commercial = compute_commercial(cost_subtotal, rules)
```

And in that method's returned dict, replace the markup/VAT entries so they read from `commercial` (keep every other key — `project_id`, `currency`, counts, `cost_subtotal`, `by_trade` — exactly as they are):

```python
            "markups": commercial["markups"],
            "selling_before_vat": commercial["selling_before_vat"],
            "vat_rate": commercial["vat_rate"],
            "vat_amount": commercial["vat_amount"],
            "grand_total": commercial["grand_total"],
```

> The numbers are identical to before (same formula), so the Phase 11 pricing tests must still pass unchanged. Remove the now-unused local variables (`m`, `overhead`, `profit`, `contingency`, `risk`, `markup_total`, `selling_before_vat`, `vat_rate`, `vat_amount`, `grand_total`) from `pricing_summary`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_commercial.py tests/pricing/ -q`
Expected: PASS — the 3 new helper tests AND all existing Phase 11 pricing tests (unchanged numbers).

- [ ] **Step 6: Commit**

```bash
git add app/services/pricing/commercial.py app/services/pricing/pricing_service.py tests/indirects/__init__.py tests/indirects/test_commercial.py
git commit -m "refactor(phase-12): extract compute_commercial helper; pricing_summary reuses it"
```

---

## Task 2: Indirects schemas + `IndirectsService.compute`

**Files:**
- Create: `app/schemas/indirects.py`, `app/services/indirects/__init__.py`, `app/services/indirects/indirects_service.py`
- Test: `tests/indirects/test_indirects_service.py`

- [ ] **Step 1: Write the schemas**

Create `app/schemas/indirects.py`:

```python
"""Schemas for the indirects engine and the full project cost rollup."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.pricing import MarkupBreakdown


class IndirectsBreakdown(BaseModel):
    percentage_based: dict[str, float] = Field(default_factory=dict)  # component -> amount
    duration_based: dict[str, float] = Field(default_factory=dict)  # role -> amount
    duration_months: int
    location: str
    location_factor: float
    subtotal_before_location: float
    total_indirects: float


class IndirectsResult(BaseModel):
    project_id: int
    currency: str
    direct_cost: float
    indirects: IndirectsBreakdown


class ProjectCostSummary(BaseModel):
    project_id: int
    currency: str
    direct_cost: float
    indirects: IndirectsBreakdown
    total_cost_base: float  # direct + indirects (the markup base)
    markups: MarkupBreakdown
    selling_before_vat: float
    vat_rate: float
    vat_amount: float
    grand_total: float
```

- [ ] **Step 2: Write the failing tests**

Create `tests/indirects/test_indirects_service.py`:

```python
from app.schemas.rules import DurationBasedRole, RulesConfig
from app.services.indirects.indirects_service import IndirectsService


class _FakeRules:
    def __init__(self, cfg):
        self._cfg = cfg

    def load(self):
        return self._cfg


def test_compute_default_percentage_based():
    # Real RulesService loads config/rules.default.json (percentages sum to 0.085).
    out = IndirectsService().compute(22000.0)
    assert out["percentage_based"]["site_supervision"] == 660.0  # 0.03 * 22000
    assert out["percentage_based"]["temporary_works"] == 440.0  # 0.02 * 22000
    assert out["duration_based"] == {}  # default monthly_rate 0 -> dropped or zero
    assert out["location_factor"] == 1.0
    assert out["subtotal_before_location"] == 1870.0  # 0.085 * 22000
    assert out["total_indirects"] == 1870.0
    assert out["duration_months"] == 0
    assert out["location"] == "default"


def test_compute_duration_based_and_location():
    cfg = RulesConfig()
    cfg.indirects.percentage_based = {"site_supervision": 0.03}
    cfg.indirects.duration_based = {
        "project_manager": DurationBasedRole(monthly_rate=5000),
        "site_engineer": DurationBasedRole(monthly_rate=3000),
    }
    # default location_factors include remote: 1.15
    svc = IndirectsService(rules_service=_FakeRules(cfg))
    out = svc.compute(10000.0, duration_months=6, location="remote")
    assert out["percentage_based"] == {"site_supervision": 300.0}
    assert out["duration_based"] == {"project_manager": 30000.0, "site_engineer": 18000.0}
    assert out["subtotal_before_location"] == 48300.0  # 300 + 48000
    assert out["location_factor"] == 1.15
    assert out["total_indirects"] == round(48300.0 * 1.15, 2)  # 55545.0


def test_compute_unknown_location_falls_back_to_default():
    cfg = RulesConfig()
    cfg.indirects.percentage_based = {"x": 0.10}
    svc = IndirectsService(rules_service=_FakeRules(cfg))
    out = svc.compute(1000.0, location="atlantis")
    assert out["location_factor"] == 1.0  # default
    assert out["total_indirects"] == 100.0
```

> Note: `test_compute_default_percentage_based` asserts `duration_based == {}`. Implement `compute` so a role whose computed amount is 0 is omitted from the `duration_based` map (keeps the breakdown clean when no duration/rates are set). If you prefer to keep zero entries, change the assertion accordingly — but the plan's implementation below omits zeros.

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_indirects_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.indirects`.

- [ ] **Step 4: Implement `compute`**

Create `app/services/indirects/__init__.py` (empty file).

Create `app/services/indirects/indirects_service.py`:

```python
"""Indirect-cost engine: percentage-of-direct components, duration-based staff
costs, and a location factor — all configurable via rules.indirects.

Pure logic — no LLM. Direct cost is read from the Phase 11 pricing summary.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pricing.commercial import compute_commercial
from app.services.pricing.pricing_service import PricingService
from app.services.rules.rules_service import RulesService


class IndirectsService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    def _rules(self):
        return self._rules_service.load()

    def compute(
        self,
        direct_cost: float,
        *,
        duration_months: int = 0,
        location: str = "default",
    ) -> dict:
        """Return the indirects breakdown for a given direct cost."""
        ind = self._rules().indirects
        percentage_based = {
            name: round(direct_cost * frac, 2)
            for name, frac in ind.percentage_based.items()
        }
        duration_based = {
            role: round(cfg.monthly_rate * duration_months, 2)
            for role, cfg in ind.duration_based.items()
            if round(cfg.monthly_rate * duration_months, 2) != 0.0
        }
        subtotal = round(
            sum(percentage_based.values()) + sum(duration_based.values()), 2
        )
        location_factor = ind.location_factors.get(
            location, ind.location_factors.get("default", 1.0)
        )
        total_indirects = round(subtotal * location_factor, 2)
        return {
            "percentage_based": percentage_based,
            "duration_based": duration_based,
            "duration_months": duration_months,
            "location": location,
            "location_factor": location_factor,
            "subtotal_before_location": subtotal,
            "total_indirects": total_indirects,
        }

    async def indirects_result(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        duration_months: int = 0,
        location: str = "default",
    ) -> dict:
        summary = await PricingService(self._rules_service).pricing_summary(db, project_id)
        direct_cost = summary["cost_subtotal"]
        return {
            "project_id": project_id,
            "currency": summary["currency"],
            "direct_cost": direct_cost,
            "indirects": self.compute(
                direct_cost, duration_months=duration_months, location=location
            ),
        }

    async def project_cost_summary(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        duration_months: int = 0,
        location: str = "default",
    ) -> dict:
        rules = self._rules()
        summary = await PricingService(self._rules_service).pricing_summary(db, project_id)
        direct_cost = summary["cost_subtotal"]
        indirects = self.compute(
            direct_cost, duration_months=duration_months, location=location
        )
        total_cost_base = round(direct_cost + indirects["total_indirects"], 2)
        commercial = compute_commercial(total_cost_base, rules)
        return {
            "project_id": project_id,
            "currency": summary["currency"],
            "direct_cost": direct_cost,
            "indirects": indirects,
            "total_cost_base": total_cost_base,
            "markups": commercial["markups"],
            "selling_before_vat": commercial["selling_before_vat"],
            "vat_rate": commercial["vat_rate"],
            "vat_amount": commercial["vat_amount"],
            "grand_total": commercial["grand_total"],
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_indirects_service.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/indirects.py app/services/indirects/__init__.py app/services/indirects/indirects_service.py tests/indirects/test_indirects_service.py
git commit -m "feat(phase-12): IndirectsService.compute — percentage/duration/location indirects"
```

---

## Task 3: Project cost rollup (`project_cost_summary`) test

**Files:**
- Test: `tests/indirects/test_indirects_service.py` (append)

> The `indirects_result` and `project_cost_summary` methods were written in Task 2; this task adds DB-level tests that exercise them end-to-end against a priced project.

- [ ] **Step 1: Write the failing tests**

Append to `tests/indirects/test_indirects_service.py`:

```python
import pytest

from app.models.boq import BOQItem
from app.models.project import Project
from app.services.indirects.indirects_service import IndirectsService as _IS


async def _seed_priced_project(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    # Two priced items totalling 22000, one excluded item that must NOT count.
    db.add_all([
        BOQItem(project_id=project.id, line_number="1", description="AC unit",
                unit="no", quantity=5, client_row_index=2, trade_category="mep",
                unit_rate=1200, total_price=6000, currency="USD"),
        BOQItem(project_id=project.id, line_number="2", description="VRF",
                unit="no", quantity=2, client_row_index=3, trade_category="mep",
                unit_rate=8000, total_price=16000, currency="USD"),
        BOQItem(project_id=project.id, line_number="3", description="Excluded",
                unit="no", quantity=1, client_row_index=4, trade_category="mep",
                unit_rate=999, total_price=999, currency="USD", is_excluded=True),
    ])
    await db.commit()
    return project.id


async def test_indirects_result_uses_direct_cost(db_session):
    pid = await _seed_priced_project(db_session)
    out = await _IS().indirects_result(db_session, pid)
    assert out["direct_cost"] == 22000.0  # excluded item not counted
    assert out["currency"] == "USD"
    assert out["indirects"]["total_indirects"] == 1870.0  # 0.085 * 22000


async def test_project_cost_summary_rolls_up_indirects_then_markups(db_session):
    pid = await _seed_priced_project(db_session)
    out = await _IS().project_cost_summary(db_session, pid)
    assert out["direct_cost"] == 22000.0
    assert out["indirects"]["total_indirects"] == 1870.0
    assert out["total_cost_base"] == 23870.0  # direct + indirects
    # markups on 23870: overhead .08, profit .10, contingency .05, risk .03 -> .26
    assert out["markups"]["markup_total"] == round(23870.0 * 0.26, 2)  # 6206.2
    assert out["selling_before_vat"] == round(23870.0 * 1.26, 2)  # 30076.2
    assert out["grand_total"] == round(23870.0 * 1.26, 2)  # vat 0
    assert out["currency"] == "USD"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_indirects_service.py -q`
Expected: PASS (5 tests total — the implementation already exists from Task 2).

- [ ] **Step 3: Commit**

```bash
git add tests/indirects/test_indirects_service.py
git commit -m "test(phase-12): cost rollup uses direct cost (excludes excluded items) + indirects then markups"
```

---

## Task 4: Indirects API router

**Files:**
- Create: `app/api/indirects.py`
- Modify: `app/main.py`
- Test: `tests/indirects/test_indirects_api.py`

Endpoints:
- `GET /api/projects/{pid}/indirects?duration_months=&location=` — the indirects breakdown only.
- `GET /api/projects/{pid}/cost-summary?duration_months=&location=` — the full rollup (direct → indirects → markups → VAT → grand total).

- [ ] **Step 1: Write the failing tests**

Create `tests/indirects/test_indirects_api.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def indirects_client():
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
        seed.add_all([
            BOQItem(project_id=project.id, line_number="1", description="AC",
                    unit="no", quantity=5, client_row_index=2, trade_category="mep",
                    unit_rate=1200, total_price=6000, currency="USD"),
            BOQItem(project_id=project.id, line_number="2", description="VRF",
                    unit="no", quantity=2, client_row_index=3, trade_category="mep",
                    unit_rate=8000, total_price=16000, currency="USD"),
        ])
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


async def test_indirects_endpoint(indirects_client):
    client, pid = indirects_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/indirects")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["direct_cost"] == 22000.0
        assert body["indirects"]["total_indirects"] == 1870.0
        assert body["indirects"]["location"] == "default"


async def test_cost_summary_endpoint(indirects_client):
    client, pid = indirects_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/cost-summary", params={"duration_months": 0})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_cost_base"] == 23870.0
        assert body["grand_total"] == round(23870.0 * 1.26, 2)


async def test_indirects_404_missing_project(indirects_client):
    client, _ = indirects_client
    async with client as c:
        r = await c.get("/api/projects/999999/indirects")
    assert r.status_code == 404


async def test_cost_summary_unknown_location_falls_back(indirects_client):
    client, pid = indirects_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/cost-summary", params={"location": "atlantis"})
        assert r.status_code == 200
        assert r.json()["indirects"]["location_factor"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_indirects_api.py -q`
Expected: FAIL — router not registered / 404s.

- [ ] **Step 3: Implement the router**

Create `app/api/indirects.py`:

```python
"""Indirects API: the project indirect-cost breakdown and the full project
cost rollup (direct -> indirects -> markups -> VAT -> grand total)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.indirects import IndirectsResult, ProjectCostSummary
from app.services.indirects.indirects_service import IndirectsService

router = APIRouter(tags=["indirects"])


@router.get("/projects/{project_id}/indirects", response_model=IndirectsResult)
async def get_indirects(
    project_id: int,
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> IndirectsResult:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await IndirectsService().indirects_result(
        db, project_id, duration_months=duration_months, location=location
    )
    return IndirectsResult(**result)


@router.get("/projects/{project_id}/cost-summary", response_model=ProjectCostSummary)
async def get_cost_summary(
    project_id: int,
    duration_months: int = Query(default=0, ge=0),
    location: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
) -> ProjectCostSummary:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await IndirectsService().project_cost_summary(
        db, project_id, duration_months=duration_months, location=location
    )
    return ProjectCostSummary(**result)
```

- [ ] **Step 4: Register the router in `app/main.py`**

Add the import (alphabetical block is fine):

```python
from app.api.indirects import router as indirects_router
```

Add the registration after the pricing router:

```python
app.include_router(indirects_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/indirects/test_indirects_api.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/indirects.py app/main.py tests/indirects/test_indirects_api.py
git commit -m "feat(phase-12): indirects + cost-summary API endpoints"
```

---

## Task 5: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, zero failures, no new skips. Baseline was 182; this phase adds 3 (commercial) + 6 (service) + 4 (API) = **13** → **195 passing** (±a couple). Hard requirement: zero failures, and the Phase 11 pricing tests still pass after the `compute_commercial` refactor.

- [ ] **Step 2: Smoke-check routes register**

Run:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'indirect' in p or 'cost-summary' in p))"
```
Expected:
```
/api/projects/{project_id}/cost-summary
/api/projects/{project_id}/indirects
```

- [ ] **Step 3: Final commit (if anything uncommitted)**

```bash
git add -A
git commit -m "test(phase-12): full suite green — indirects engine + project cost rollup"
```

---

## Spec Coverage Self-Review

| Phase 12 spec requirement (spec §6 cap 10) | Task |
|---|---|
| Percentage-based indirects (of direct cost) | 2 |
| Duration-based indirects (monthly staff rates × months) | 2 |
| Location factor | 2 |
| Fully configurable from rules.indirects | 2 |
| Roll indirects into the project cost (direct → indirects → markups → VAT) | 1, 2, 3 |
| API surfacing (indirects + full cost summary) | 4 |
| Reuse Phase 11 direct cost (excludes excluded items) | 2, 3 |
| DRY markup/VAT (no duplicated formula) | 1 (shared `compute_commercial`) |
| Root conventions (db param, rules-injectable, no migration) | all |

**Design note (markup base):** the `cost-summary` applies markups on `direct + indirects` (the contractor model — preliminaries/indirects are cost, profit/overhead/contingency/risk apply on the total). Phase 11's `pricing_summary` keeps its existing "direct-cost-only" markup view; `cost-summary` is the complete project total. Both are exposed; they intentionally differ when indirects are non-zero. Duration (months) and location are request parameters (no project schema change); a future phase can persist them on the project if desired.

**Deferred / out of scope:** historical-price benchmarking (Phase 13), client deliverables/dashboard (Phase 14), React UI (Phase 6C). Per-trade or per-component location factors (only a single project-level location factor is applied) are not implemented; the single factor multiplies the whole indirect subtotal, which a later phase can refine without changing the rollup contract.
