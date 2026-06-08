# Phase 8A — BOQ Packaging (generation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group a project's classified BOQ items into trade-based procurement packages (respecting configurable sizing), generate package codes from the naming rules, persist `Package` rows with their `BOQItem`s assigned, and expose generate/list/detail APIs.

**Architecture:** A `PackagingService` loads the project's classified `BOQItem`s (Phase 7B), groups them by `trade_category`, splits any group exceeding `rules.packaging.max_items_per_package` into sequential packages, generates each code via `rules.naming.package_code_format` + `trade_abbreviations` (Phase 6B), persists `Package` rows (Phase 6A), and sets each item's `package_id`. Regeneration is idempotent (clears the project's existing packages + unassigns items first). Uncategorized items (`trade_category is None`) are left unassigned and reported. API: `POST /packages/generate`, `GET /packages`, `GET /packages/{id}`.

**Tech Stack:** Python 3.11, async SQLAlchemy, FastAPI, httpx (ASGI tests), pytest.

**Reference (grouping/code approach):** `bidops-ai/backend/app/services/packaging_service.py` (`generate_packages_from_boq`, code format `PKG-{project_code}-{trade_abbr}-{seq:03d}`). Reuse the approach on the root models + configurable rules.

**Decomposition note:** Plan **8A** of Phase 8. Siblings (separate plans): **8B** link relevant documents to packages via semantic search (ChromaDB), **8C** package folder structure + Packages Register.xlsx + Package Brief PDF (graceful WeasyPrint). 8A is the deterministic core both build on. Consumes 6A (`Package`/`BOQItem`), 6B (`RulesConfig`), 7B (classified BOQ items).

---

## File Structure

- `app/services/packaging/__init__.py` — CREATE (empty).
- `app/services/packaging/packaging_service.py` — CREATE: `PackagingService.generate(...)`, `list_packages(...)`, `get_package(...)`.
- `app/schemas/packaging.py` — CREATE: `PackageResponse`, `PackageDetailResponse`, `PackagingResult`.
- `app/api/packaging.py` — CREATE: POST generate + GET list + GET detail.
- `app/main.py` — MODIFY: register packaging router.
- `tests/packaging/__init__.py`, `tests/packaging/test_*.py` — CREATE.

---

## Task 1: `PackagingService.generate` (group + size + code + persist)

**Files:** Create `app/services/packaging/__init__.py` (empty), `app/services/packaging/packaging_service.py`; Test `tests/packaging/__init__.py` (empty), `tests/packaging/test_packaging_service.py`

- [ ] **Step 1: Write the failing test `tests/packaging/test_packaging_service.py`**

```python
import json
import pathlib

from app.schemas.rules import RulesConfig


def _rules():
    return RulesConfig.model_validate(
        json.loads(pathlib.Path("config/rules.default.json").read_text(encoding="utf-8"))
    )


async def _seed(db, trades):
    """Create a project + BOQItems with the given trade_category list."""
    from app.models.project import Project
    from app.models.boq import BOQItem

    project = Project(name="P")
    db.add(project)
    await db.flush()
    for i, trade in enumerate(trades, start=1):
        db.add(
            BOQItem(
                project_id=project.id,
                line_number=str(i),
                description=f"item {i}",
                unit="no",
                quantity=1,
                client_row_index=i,
                trade_category=trade,
                requires_review=trade is None,
            )
        )
    await db.commit()
    return project.id


async def test_generate_groups_by_trade_and_assigns_items(db_session):
    from sqlalchemy import select
    from app.models.boq import BOQItem
    from app.models.package import Package
    from app.services.packaging.packaging_service import PackagingService

    pid = await _seed(db_session, ["concrete", "concrete", "mep", None])

    result = await PackagingService(rules=_rules()).generate(db_session, pid)

    assert result["packages_created"] == 2          # concrete + mep
    assert result["items_assigned"] == 3
    assert result["items_unassigned"] == 1          # the None-trade item
    assert result["by_trade"]["concrete"] == 1
    assert result["by_trade"]["mep"] == 1

    packages = (await db_session.execute(
        select(Package).where(Package.project_id == pid)
    )).scalars().all()
    assert len(packages) == 2
    concrete = next(p for p in packages if p.trade_category == "concrete")
    assert concrete.total_items == 2
    assert concrete.code.startswith("PKG-")
    assert "CON" in concrete.code            # trade_abbreviations: concrete -> CON
    # items got their package_id set
    assigned = (await db_session.execute(
        select(BOQItem).where(BOQItem.trade_category == "concrete")
    )).scalars().all()
    assert all(i.package_id == concrete.id for i in assigned)


async def test_generate_splits_oversized_trade_group(db_session):
    from sqlalchemy import select
    from app.models.package import Package
    from app.services.packaging.packaging_service import PackagingService

    pid = await _seed(db_session, ["mep"] * 5)
    rules = _rules()
    rules.packaging.max_items_per_package = 2     # force splitting

    result = await PackagingService(rules=rules).generate(db_session, pid)

    mep_pkgs = (await db_session.execute(
        select(Package).where(Package.project_id == pid)
    )).scalars().all()
    assert len(mep_pkgs) == 3                      # ceil(5/2)
    assert result["packages_created"] == 3
    assert sum(p.total_items for p in mep_pkgs) == 5
    assert len({p.code for p in mep_pkgs}) == 3    # unique codes


async def test_generate_is_idempotent(db_session):
    from sqlalchemy import select, func
    from app.models.package import Package
    from app.services.packaging.packaging_service import PackagingService

    pid = await _seed(db_session, ["concrete", "mep"])
    svc = PackagingService(rules=_rules())
    await svc.generate(db_session, pid)
    await svc.generate(db_session, pid)            # re-run

    count = (await db_session.execute(
        select(func.count()).select_from(Package).where(Package.project_id == pid)
    )).scalar_one()
    assert count == 2                              # not duplicated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_service.py -v`
Expected: FAIL (ModuleNotFoundError). Create the two empty `__init__.py` first.

- [ ] **Step 3: Create `app/services/packaging/packaging_service.py`**

```python
"""Groups classified BOQ items into trade-based procurement packages."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.package import Package
from app.schemas.rules import RulesConfig
from app.services.rules import get_rules_service


class PackagingService:
    """Generate, list, and inspect trade packages for a project."""

    def __init__(self, rules: RulesConfig | None = None) -> None:
        self._rules = rules or get_rules_service().load()

    def _project_code(self, project_id: int) -> str:
        return f"P{project_id:04d}"

    def _package_code(self, project_id: int, trade: str, seq: int) -> str:
        abbr = self._rules.naming.trade_abbreviations.get(trade, trade[:3].upper())
        try:
            return self._rules.naming.package_code_format.format(
                project_code=self._project_code(project_id),
                trade_abbr=abbr,
                seq=seq,
            )
        except (KeyError, IndexError, ValueError):
            return f"PKG-{self._project_code(project_id)}-{abbr}-{seq:03d}"

    async def generate(self, db: AsyncSession, project_id: int) -> dict:
        """(Re)generate packages for a project from its classified BOQ items.

        Idempotent: deletes existing packages + unassigns items first, then
        groups classified items by trade and splits groups larger than
        rules.packaging.max_items_per_package. Uncategorized items
        (trade_category is None) are left unassigned and counted.
        """
        # Reset: unassign all items, delete existing packages for the project.
        await db.execute(
            update(BOQItem)
            .where(BOQItem.project_id == project_id)
            .values(package_id=None)
        )
        await db.execute(delete(Package).where(Package.project_id == project_id))
        await db.flush()

        items = (
            await db.execute(
                select(BOQItem)
                .where(BOQItem.project_id == project_id)
                .order_by(BOQItem.client_row_index)
            )
        ).scalars().all()

        groups: dict[str, list[BOQItem]] = defaultdict(list)
        unassigned = 0
        for item in items:
            if item.trade_category:
                groups[item.trade_category].append(item)
            else:
                unassigned += 1

        max_items = max(1, self._rules.packaging.max_items_per_package)
        by_trade: Counter[str] = Counter()
        seq = 0
        assigned = 0

        for trade in sorted(groups):
            trade_items = groups[trade]
            # split into chunks of at most max_items
            chunks = [
                trade_items[i : i + max_items]
                for i in range(0, len(trade_items), max_items)
            ]
            multi = len(chunks) > 1
            for part, chunk in enumerate(chunks, start=1):
                seq += 1
                name = f"{trade.replace('_', ' ').title()} Works"
                if multi:
                    name = f"{name} (Part {part})"
                package = Package(
                    project_id=project_id,
                    name=name,
                    code=self._package_code(project_id, trade, seq),
                    trade_category=trade,
                    total_items=len(chunk),
                )
                db.add(package)
                await db.flush()  # assign package.id
                for item in chunk:
                    item.package_id = package.id
                by_trade[trade] += 1
                assigned += len(chunk)

        await db.commit()
        return {
            "project_id": project_id,
            "packages_created": seq,
            "items_assigned": assigned,
            "items_unassigned": unassigned,
            "by_trade": dict(by_trade),
        }

    async def list_packages(self, db: AsyncSession, project_id: int) -> list[Package]:
        result = await db.execute(
            select(Package)
            .where(Package.project_id == project_id)
            .order_by(Package.code)
        )
        return list(result.scalars().all())

    async def get_package(self, db: AsyncSession, package_id: int) -> Package | None:
        return await db.get(Package, package_id)

    async def get_package_items(
        self, db: AsyncSession, package_id: int
    ) -> list[BOQItem]:
        result = await db.execute(
            select(BOQItem)
            .where(BOQItem.package_id == package_id)
            .order_by(BOQItem.client_row_index)
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_service.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/packaging/__init__.py app/services/packaging/packaging_service.py tests/packaging/__init__.py tests/packaging/test_packaging_service.py
git commit -m "feat(packaging): PackagingService — group classified BOQ items into trade packages"
```

---

## Task 2: Packaging schemas + API

**Files:** Create `app/schemas/packaging.py`, `app/api/packaging.py`; Modify `app/main.py`; Test `tests/packaging/test_packaging_api.py`

- [ ] **Step 1: Write the failing test `tests/packaging/test_packaging_api.py`**

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def pkg_client(tmp_path):
    from app.models import Base
    from app.models.project import Project
    from app.models.boq import BOQItem
    from app.database import get_db
    from app.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="P")
        seed.add(project)
        await seed.flush()
        for i, trade in enumerate(["concrete", "concrete", "mep"], start=1):
            seed.add(BOQItem(
                project_id=project.id, line_number=str(i), description=f"d{i}",
                unit="no", quantity=1, client_row_index=i, trade_category=trade,
            ))
        await seed.commit()
        project_id = project.id

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, project_id
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_generate_list_detail(pkg_client):
    client, pid = pkg_client
    async with client:
        gen = await client.post(f"/api/projects/{pid}/packages/generate")
        assert gen.status_code == 200, gen.text
        assert gen.json()["packages_created"] == 2

        lst = await client.get(f"/api/projects/{pid}/packages")
        assert lst.status_code == 200
        packages = lst.json()
        assert len(packages) == 2
        concrete = next(p for p in packages if p["trade_category"] == "concrete")
        assert concrete["total_items"] == 2

        detail = await client.get(f"/api/projects/{pid}/packages/{concrete['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["code"] == concrete["code"]
        assert len(body["items"]) == 2


async def test_generate_404_missing_project(pkg_client):
    client, _ = pkg_client
    async with client:
        r = await client.post("/api/projects/999999/packages/generate")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/schemas/packaging.py`**

```python
"""Schemas for package generation results and package views."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.boq import BOQItemResponse


class PackageResponse(BaseModel):
    id: int
    code: str
    name: str
    trade_category: str
    status: str
    total_items: int

    model_config = {"from_attributes": True}


class PackageDetailResponse(PackageResponse):
    items: list[BOQItemResponse] = []


class PackagingResult(BaseModel):
    project_id: int
    packages_created: int
    items_assigned: int
    items_unassigned: int
    by_trade: dict[str, int]
```

- [ ] **Step 4: Create `app/api/packaging.py`**

```python
"""Packaging API: generate trade packages from BOQ items, list, and inspect."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.boq import BOQItemResponse
from app.schemas.packaging import (
    PackageDetailResponse,
    PackageResponse,
    PackagingResult,
)
from app.services.packaging.packaging_service import PackagingService

router = APIRouter(prefix="/projects/{project_id}/packages", tags=["packaging"])


@router.post("/generate", response_model=PackagingResult)
async def generate_packages(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> PackagingResult:
    """(Re)generate trade packages from the project's classified BOQ items."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    summary = await PackagingService().generate(db, project_id)
    return PackagingResult(**summary)


@router.get("", response_model=list[PackageResponse])
async def list_packages(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[PackageResponse]:
    packages = await PackagingService().list_packages(db, project_id)
    return [PackageResponse.model_validate(p) for p in packages]


@router.get("/{package_id}", response_model=PackageDetailResponse)
async def package_detail(
    project_id: int,
    package_id: int,
    db: AsyncSession = Depends(get_db),
) -> PackageDetailResponse:
    svc = PackagingService()
    package = await svc.get_package(db, package_id)
    if package is None or package.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    items = await svc.get_package_items(db, package_id)
    detail = PackageDetailResponse.model_validate(package)
    detail.items = [BOQItemResponse.model_validate(i) for i in items]
    return detail
```

- [ ] **Step 5: Register the router in `app/main.py`**

Add with the other imports:
```python
from app.api.packaging import router as packaging_router
```
And register alongside the others:
```python
app.include_router(packaging_router, prefix="/api")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_api.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add app/schemas/packaging.py app/api/packaging.py app/main.py tests/packaging/test_packaging_api.py
git commit -m "feat(packaging): generate/list/detail package API"
```

---

## Task 3: Full-suite check

- [ ] **Step 1: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS (6A + 6B + 7A + 7B + 8A). Report the count.

- [ ] **Step 2: Boot smoke**

Run: `.venv/Scripts/python.exe -c "import app.main; print('pkg routes:', [r.path for r in app.main.app.routes if '/packages' in getattr(r,'path','')])"`
Expected: shows the generate/list/detail package routes.

---

## Self-Review (completed by author)

- **Spec coverage:** Implements plan.md capability 4 (packaging) core: group classified BOQ items into trade packages with configurable sizing + naming, persist `Package` + assign `BOQItem`s, generate/list/detail API. Sizing (`max_items_per_package`) and codes (`package_code_format` + `trade_abbreviations`) both come from the configurable rules (6B). Uncategorized items surfaced (not silently dropped).
- **Out of scope (sibling plans):** document→package linking via semantic search (8B), folder structure + Packages Register.xlsx + Package Brief PDF (8C), supplier targeting/RFQ (Phase 9).
- **Placeholder scan:** All code inline + complete (service, schemas, API, tests). No TODOs.
- **Type consistency:** `PackagingService.generate/list_packages/get_package/get_package_items` signatures match API usage and tests. `PackagingResult(**summary)` keys (project_id/packages_created/items_assigned/items_unassigned/by_trade) match the service return. `Package` columns written (project_id/name/code/trade_category/total_items) all exist (Phase 6A). `PackageResponse` uses `from_attributes`; reuses `BOQItemResponse` from 7B.
- **Idempotency:** `generate` resets (unassign items + delete packages) before regenerating — verified by `test_generate_is_idempotent`. Splitting verified by `test_generate_splits_oversized_trade_group` (max=2 → 3 packages for 5 items).
- **Test isolation:** service tests use the in-memory `db_session` fixture; API test overrides `get_db` with a temp engine seeded with a project + classified items and clears the override — never touches `data/bidops.db`.
