# Phase 7B — BOQ Excel Parsing + Trade Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse a client BOQ Excel into structured `BOQItem` rows (auto-detecting header row + columns, propagating section headers, standardizing units) and classify each line into a configurable trade category, exposed via a parse + list API.

**Architecture:** Three focused services under `app/services/boq/`: a `boq_parser` (openpyxl — no pandas, matching the root app's stack) that turns a workbook into `ParsedBoqRow`s; a `trade_classifier` that maps a description to a trade using the configurable `rules.packaging.trade_categories` (from Phase 6B) + `rules.measurement.unit_mappings` for unit normalization; and a `boq_service` that orchestrates parse → classify → persist `BOQItem`s (Phase 6A model) for a project. API: `POST /api/projects/{id}/boq/parse` (upload xlsx) and `GET /api/projects/{id}/boq`. Deterministic and fully testable without the LLM (LLM-assisted classification of unmatched items is a noted future enhancement).

**Tech Stack:** Python 3.11, openpyxl, async SQLAlchemy, FastAPI, httpx (ASGI tests), pytest.

**Reference (heuristics to mirror):** `bidops-ai/backend/app/services/boq_service.py` — column-name aliases (`description`/`qty`/`unit`/`item`/`section`), unit mappings, section-vs-item detection. Reuse the *approach*; implement on openpyxl + the configurable rules, not pandas.

**Decomposition note:** Plan **7B** of Phase 7. Sibling: **7C** doc classification + addenda versioning. Consumes 6A (`BOQItem`) + 6B (`RulesConfig`). Feeds Phase 8 (packaging groups BOQ items by trade).

---

## File Structure

- `app/services/boq/__init__.py` — CREATE.
- `app/services/boq/boq_parser.py` — CREATE: `ParsedBoqRow` + `parse_boq_workbook()`.
- `app/services/boq/trade_classifier.py` — CREATE: `classify_trade()`.
- `app/services/boq/boq_service.py` — CREATE: `BOQService.parse_and_store()`, `list_items()`.
- `app/schemas/boq.py` — CREATE: `BOQItemResponse`, `BOQParseResult`.
- `app/api/boq.py` — CREATE: POST parse + GET list.
- `app/main.py` — MODIFY: register boq router.
- `tests/boq/__init__.py`, `tests/boq/test_*.py` — CREATE.

---

## Task 1: BOQ parser (openpyxl)

**Files:** Create `app/services/boq/__init__.py` (empty), `app/services/boq/boq_parser.py`; Test `tests/boq/__init__.py` (empty), `tests/boq/test_boq_parser.py`

- [ ] **Step 1: Write the failing test `tests/boq/test_boq_parser.py`**

```python
from openpyxl import Workbook


def _make_boq(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Title row spanning the sheet", None, None, None])  # noise row 1
    ws.append(["Item", "Description", "Unit", "Qty"])              # header row 2
    ws.append([None, "DIVISION 2 - CONCRETE WORKS", None, None])   # section (no qty)
    ws.append(["2.1", "Reinforced concrete C35/45 in columns", "cum", 5400])
    ws.append(["2.2", "High-tensile reinforcement steel", "ton", 4900])
    ws.append([None, "DIVISION 3 - HVAC", None, None])             # section
    ws.append(["3.1", "Supply and install AHU with HEPA filter", "nr", 22])
    wb.save(path)


def test_parse_detects_header_sections_units(tmp_path):
    from app.services.boq.boq_parser import parse_boq_workbook
    from app.schemas.rules import RulesConfig

    f = tmp_path / "boq.xlsx"
    _make_boq(f)
    rows = parse_boq_workbook(str(f), RulesConfig())

    # 3 priced items (section rows excluded)
    assert len(rows) == 3
    first = rows[0]
    assert first.description.startswith("Reinforced concrete")
    assert first.unit == "m3"            # "cum" standardized via unit_mappings
    assert first.quantity == 5400
    assert first.section == "DIVISION 2 - CONCRETE WORKS"
    assert rows[2].section == "DIVISION 3 - HVAC"
    assert rows[2].unit == "no"          # "nr" -> "no"
    assert rows[0].client_row_index == 4  # 1-based Excel row of the item
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_boq_parser.py -v`
Expected: FAIL (ModuleNotFoundError). Create the two empty `__init__.py` first.

- [ ] **Step 3: Create `app/services/boq/boq_parser.py`**

```python
"""BOQ Excel parser (openpyxl): workbook -> structured, unit-normalized rows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from app.schemas.rules import RulesConfig

# Header-cell aliases -> canonical column key.
_COLUMN_ALIASES: dict[str, list[str]] = {
    "line_number": ["item", "item no", "no", "no.", "s.no", "sno", "ref", "line"],
    "description": ["description", "desc", "item description", "particulars", "work item"],
    "unit": ["unit", "uom", "u/m", "u.o.m"],
    "quantity": ["quantity", "qty", "qnty", "q'ty", "quantities"],
    "section": ["section", "division", "category", "trade", "bill"],
}

_SHEET_HINTS = ["boq", "bill", "quantity", "pricing", "boqs"]
_MAX_HEADER_SCAN = 20


@dataclass
class ParsedBoqRow:
    """One parsed BOQ line (a priced item, not a section header)."""

    line_number: str | None
    section: str | None
    description: str
    unit: str | None
    quantity: float | None
    client_row_index: int  # 1-based Excel row number


def _norm(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def _pick_sheet(wb):
    for name in wb.sheetnames:
        if any(h in name.lower() for h in _SHEET_HINTS):
            return wb[name]
    return wb[wb.sheetnames[0]]


def _find_header(ws) -> tuple[int, dict[int, str]]:
    """Return (1-based header row index, {col_index: canonical_key}).

    Picks the first row (within the scan window) that maps both a description
    column and at least one of unit/quantity. Falls back to row 1.
    """
    for r in range(1, min(ws.max_row, _MAX_HEADER_SCAN) + 1):
        col_map: dict[int, str] = {}
        for c in range(1, ws.max_column + 1):
            cell = _norm(ws.cell(row=r, column=c).value)
            if not cell:
                continue
            for key, aliases in _COLUMN_ALIASES.items():
                if cell in aliases and key not in col_map.values():
                    col_map[c] = key
                    break
        if "description" in col_map.values() and (
            "quantity" in col_map.values() or "unit" in col_map.values()
        ):
            return r, col_map
    return 1, {}


def _standardize_unit(raw: object, rules: RulesConfig) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    key = str(raw).strip().lower()
    return rules.measurement.unit_mappings.get(key, str(raw).strip())


def parse_boq_workbook(file_path: str, rules: RulesConfig) -> list[ParsedBoqRow]:
    """Parse a BOQ workbook into priced rows; section headers propagate down."""
    wb = load_workbook(file_path, read_only=True, data_only=True)
    try:
        ws = _pick_sheet(wb)
        header_row, col_map = _find_header(ws)
        if not col_map:
            return []
        col_by_key = {v: k for k, v in col_map.items()}
        desc_col = col_by_key.get("description")
        qty_col = col_by_key.get("quantity")
        unit_col = col_by_key.get("unit")
        line_col = col_by_key.get("line_number")

        rows: list[ParsedBoqRow] = []
        current_section: str | None = None

        for r in range(header_row + 1, ws.max_row + 1):
            desc = ws.cell(row=r, column=desc_col).value if desc_col else None
            if desc is None or str(desc).strip() == "":
                continue
            description = str(desc).strip()
            qty_val = ws.cell(row=r, column=qty_col).value if qty_col else None
            quantity = _coerce_float(qty_val)

            # Row with a description but no numeric quantity = section header.
            if quantity is None:
                current_section = description
                continue

            rows.append(
                ParsedBoqRow(
                    line_number=(
                        str(ws.cell(row=r, column=line_col).value).strip()
                        if line_col and ws.cell(row=r, column=line_col).value is not None
                        else None
                    ),
                    section=current_section,
                    description=description,
                    unit=_standardize_unit(
                        ws.cell(row=r, column=unit_col).value if unit_col else None,
                        rules,
                    ),
                    quantity=quantity,
                    client_row_index=r,
                )
            )
        return rows
    finally:
        wb.close()


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_boq_parser.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/boq/__init__.py app/services/boq/boq_parser.py tests/boq/__init__.py tests/boq/test_boq_parser.py
git commit -m "feat(boq): openpyxl BOQ parser (header/column detection, sections, unit normalization)"
```

---

## Task 2: Trade classifier (configurable rules)

**Files:** Create `app/services/boq/trade_classifier.py`; Test `tests/boq/test_trade_classifier.py`

- [ ] **Step 1: Write the failing test `tests/boq/test_trade_classifier.py`**

```python
def test_classify_uses_rules_trade_categories():
    from app.services.boq.trade_classifier import classify_trade
    from app.schemas.rules import RulesConfig

    rules = RulesConfig.model_validate(
        __import__("json").loads(
            __import__("pathlib").Path("config/rules.default.json").read_text(encoding="utf-8")
        )
    )

    cat, conf = classify_trade("Reinforced concrete C35/45 in columns", rules)
    assert cat == "concrete" and conf > 0

    cat, conf = classify_trade("Supply and install HVAC ductwork", rules)
    assert cat == "mep"

    cat, conf = classify_trade("Excavation in all types of soil", rules)
    assert cat == "civil"

    cat, conf = classify_trade("Internal painting to walls", rules)
    assert cat == "finishes"

    cat, conf = classify_trade("Bespoke unmatched widget assembly", rules)
    assert cat is None and conf == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_trade_classifier.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/services/boq/trade_classifier.py`**

```python
"""Deterministic trade classification from the configurable rules keyword map."""

from __future__ import annotations

from app.schemas.rules import RulesConfig


def classify_trade(description: str, rules: RulesConfig) -> tuple[str | None, float]:
    """Classify a BOQ description into a trade category.

    Matches keywords from rules.packaging.trade_categories (case-insensitive,
    substring). Returns (category, confidence) where confidence scales with the
    number of distinct keyword hits (capped at 1.0). Unmatched -> (None, 0.0),
    which downstream marks the item as requiring review.
    """
    text = description.lower()
    best_cat: str | None = None
    best_hits = 0
    for category, keywords in rules.packaging.trade_categories.items():
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = category
    if best_cat is None:
        return None, 0.0
    # 1 hit -> 0.6, 2 -> 0.8, 3+ -> capped near 1.0
    confidence = min(1.0, 0.4 + 0.2 * best_hits)
    return best_cat, round(confidence, 3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_trade_classifier.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/boq/trade_classifier.py tests/boq/test_trade_classifier.py
git commit -m "feat(boq): rules-driven trade classifier"
```

---

## Task 3: `BOQService` (parse → classify → persist)

**Files:** Create `app/services/boq/boq_service.py`; Test `tests/boq/test_boq_service.py`

- [ ] **Step 1: Write the failing test `tests/boq/test_boq_service.py`**

```python
from openpyxl import Workbook


def _make_boq(path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty"])
    ws.append(["1.1", "Reinforced concrete in raft", "cum", 6800])
    ws.append(["1.2", "Supply LV electrical distribution boards", "nr", 86])
    ws.append(["1.3", "Bespoke unmatched widget", "no", 3])
    wb.save(path)


async def test_parse_and_store_creates_classified_items(db_session, tmp_path):
    from sqlalchemy import select
    from app.models.boq import BOQItem
    from app.models.project import Project
    from app.schemas.rules import RulesConfig
    from app.services.boq.boq_service import BOQService

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()

    f = tmp_path / "boq.xlsx"
    _make_boq(f)

    result = await BOQService(rules=RulesConfig.model_validate(
        __import__("json").loads(
            __import__("pathlib").Path("config/rules.default.json").read_text(encoding="utf-8")
        )
    )).parse_and_store(db_session, project.id, str(f))

    assert result["total"] == 3
    items = (await db_session.execute(
        select(BOQItem).where(BOQItem.project_id == project.id)
    )).scalars().all()
    assert len(items) == 3
    by_desc = {i.description: i for i in items}
    assert by_desc["Reinforced concrete in raft"].trade_category == "concrete"
    assert by_desc["Supply LV electrical distribution boards"].trade_category == "mep"
    # unmatched -> no category + flagged for review
    widget = by_desc["Bespoke unmatched widget"]
    assert widget.trade_category is None
    assert widget.requires_review is True
    assert result["uncategorized"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_boq_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `app/services/boq/boq_service.py`**

```python
"""Orchestrates BOQ parsing + trade classification + persistence."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.schemas.rules import RulesConfig
from app.services.boq.boq_parser import parse_boq_workbook
from app.services.boq.trade_classifier import classify_trade
from app.services.rules import get_rules_service


class BOQService:
    """Parse a BOQ workbook into classified, persisted BOQItem rows."""

    def __init__(self, rules: RulesConfig | None = None) -> None:
        self._rules = rules or get_rules_service().load()

    async def parse_and_store(
        self, db: AsyncSession, project_id: int, file_path: str
    ) -> dict:
        """Parse the workbook, classify each row, persist BOQItem rows.

        Returns a summary: {total, classified, uncategorized, by_trade}.
        """
        rows = parse_boq_workbook(file_path, self._rules)
        by_trade: Counter[str] = Counter()
        uncategorized = 0

        for idx, row in enumerate(rows, start=1):
            category, confidence = classify_trade(row.description, self._rules)
            if category is None:
                uncategorized += 1
            else:
                by_trade[category] += 1
            db.add(
                BOQItem(
                    project_id=project_id,
                    line_number=row.line_number or str(idx),
                    section=row.section,
                    description=row.description,
                    unit=row.unit,
                    quantity=row.quantity,
                    client_row_index=row.client_row_index,
                    trade_category=category,
                    classification_confidence=confidence,
                    requires_review=category is None,
                )
            )
        await db.commit()
        return {
            "total": len(rows),
            "classified": len(rows) - uncategorized,
            "uncategorized": uncategorized,
            "by_trade": dict(by_trade),
        }

    async def list_items(
        self, db: AsyncSession, project_id: int
    ) -> list[BOQItem]:
        result = await db.execute(
            select(BOQItem)
            .where(BOQItem.project_id == project_id)
            .order_by(BOQItem.client_row_index)
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_boq_service.py -v`
Expected: PASS.

Note: `BOQItem.line_number` is nullable (Phase 6A); we still set a fallback index. If `BOQItem` has no `classification_confidence`/`requires_review` columns, align field names to the actual model (it does, per Phase 6A port).

- [ ] **Step 5: Commit**

```bash
git add app/services/boq/boq_service.py tests/boq/test_boq_service.py
git commit -m "feat(boq): BOQService parse+classify+persist with summary"
```

---

## Task 4: BOQ API (parse upload + list)

**Files:** Create `app/schemas/boq.py`, `app/api/boq.py`; Modify `app/main.py`; Test `tests/boq/__init__.py` exists; `tests/boq/test_boq_api.py`

- [ ] **Step 1: Write the failing test `tests/boq/test_boq_api.py`**

```python
import io

import httpx
import pytest
import pytest_asyncio
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _boq_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty"])
    ws.append(["1.1", "Reinforced concrete in raft", "cum", 6800])
    ws.append(["1.2", "Supply and install HVAC ductwork", "sqm", 31000])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest_asyncio.fixture
async def boq_client(tmp_path):
    """ASGI client whose get_db yields a fresh in-memory DB seeded with a project."""
    from app.models import Base
    from app.models.project import Project
    from app.database import get_db
    from app.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="P")
        seed.add(project)
        await seed.commit()
        project_id = project.id

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    yield client, project_id
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_parse_and_list_boq(boq_client):
    client, project_id = boq_client
    async with client:
        files = {"file": ("boq.xlsx", _boq_bytes(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = await client.post(f"/api/projects/{project_id}/boq/parse", files=files)
        assert r.status_code == 200, r.text
        summary = r.json()
        assert summary["total"] == 2
        assert summary["by_trade"].get("concrete") == 1
        assert summary["by_trade"].get("mep") == 1

        lst = await client.get(f"/api/projects/{project_id}/boq")
        assert lst.status_code == 200
        items = lst.json()
        assert len(items) == 2
        assert {i["trade_category"] for i in items} == {"concrete", "mep"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_boq_api.py -v`
Expected: FAIL (no router / schema).

- [ ] **Step 3: Create `app/schemas/boq.py`**

```python
"""Schemas for BOQ parse results and item listing."""

from __future__ import annotations

from pydantic import BaseModel


class BOQItemResponse(BaseModel):
    id: int
    line_number: str | None
    section: str | None
    description: str
    unit: str | None
    quantity: float | None
    trade_category: str | None
    classification_confidence: float | None
    requires_review: bool

    model_config = {"from_attributes": True}


class BOQParseResult(BaseModel):
    project_id: int
    total: int
    classified: int
    uncategorized: int
    by_trade: dict[str, int]
```

- [ ] **Step 4: Create `app/api/boq.py`**

```python
"""BOQ API: parse an uploaded BOQ workbook and list parsed items."""

from __future__ import annotations

import tempfile
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.boq import BOQItemResponse, BOQParseResult
from app.services.boq.boq_service import BOQService

router = APIRouter(prefix="/projects/{project_id}/boq", tags=["boq"])

_ALLOWED = {".xlsx", ".xls"}


@router.post("/parse", response_model=BOQParseResult)
async def parse_boq(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> BOQParseResult:
    """Parse + classify + persist a BOQ workbook for a project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported BOQ file type: {ext}")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / (file.filename or "boq.xlsx")
        async with aiofiles.open(path, "wb") as out:
            await out.write(await file.read())
        summary = await BOQService().parse_and_store(db, project_id, str(path))

    return BOQParseResult(project_id=project_id, **summary)


@router.get("", response_model=list[BOQItemResponse])
async def list_boq(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[BOQItemResponse]:
    """List parsed BOQ items for a project, ordered by source row."""
    items = await BOQService().list_items(db, project_id)
    return [BOQItemResponse.model_validate(i) for i in items]
```

- [ ] **Step 5: Register the router in `app/main.py`**

Add an import with the others:

```python
from app.api.boq import router as boq_router
```

And register alongside the other `app.include_router(..., prefix="/api")` lines:

```python
app.include_router(boq_router, prefix="/api")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/boq/test_boq_api.py -v`
Expected: PASS (2 items, concrete + mep).

- [ ] **Step 7: Commit**

```bash
git add app/schemas/boq.py app/api/boq.py app/main.py tests/boq/test_boq_api.py
git commit -m "feat(boq): POST /boq/parse + GET /boq endpoints"
```

---

## Task 5: Full-suite check

- [ ] **Step 1: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS (6A + 6B + 7A + 7B). Report the count.

- [ ] **Step 2: Boot smoke**

Run: `.venv/Scripts/python.exe -c "import app.main; print('boq routes:', [r.path for r in app.main.app.routes if '/boq' in getattr(r,'path','')])"`
Expected: shows `/api/projects/{project_id}/boq/parse` and `/api/projects/{project_id}/boq`.

---

## Self-Review (completed by author)

- **Spec coverage:** Implements "BOQ Excel parsing + trade classification" — parse (header/column auto-detect, section propagation, unit normalization via configurable `unit_mappings`), classify (configurable `trade_categories`), persist `BOQItem` rows, parse + list API. Unmatched items get `trade_category=None` + `requires_review=True` (human-in-the-loop, matching the project's evidence/HITL ethos).
- **Out of scope (correct):** LLM-assisted classification of unmatched items (future enhancement — the deterministic classifier + requires_review flag is sufficient and keeps tests LLM-free); packaging/grouping (Phase 8); BOQ editing UI (6C/8 frontend).
- **Placeholder scan:** All code inline and complete (parser, classifier, service, schema, API, tests). No TODOs.
- **Type consistency:** `ParsedBoqRow` fields flow into `BOQItem` columns (Phase 6A: line_number/section/description/unit/quantity/client_row_index/trade_category/classification_confidence/requires_review — all exist). `parse_and_store(db, project_id, file_path)` and `list_items(db, project_id)` signatures consistent across service, API, and tests. `BOQParseResult(**summary)` keys (total/classified/uncategorized/by_trade) match the service's return dict.
- **Test isolation:** parser/classifier tests use `tmp_path` + `RulesConfig`; service test uses the in-memory `db_session` fixture; API test overrides `get_db` with a temp in-memory engine seeded with a project and clears the override after — never touches `data/bidops.db`.
- **DB-dependency note:** `BOQService` is constructed inside the endpoints (not module-singleton) and receives the request-scoped session, so the API test's `dependency_overrides[get_db]` fully controls persistence.
