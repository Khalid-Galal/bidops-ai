# Phase 13 — Historical Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a historical price-learning engine: a persistent `HistoricalPrice` corpus (seeded by importing rate sheets and by indexing a project's priced BOQ), price/benchmark suggestions for new BOQ items via fuzzy similarity with full traceability to the source records, and a correction-feedback loop that folds accepted/corrected rates back into the corpus.

**Architecture:** Pure logic, no Gemini key needed. A new `HistoricalPrice` table (decoupled from projects) holds the corpus. `HistoricalService` matches a query description against the corpus using the existing Phase 11 `line_item_matcher.match_score` (deterministic token-Jaccard + difflib; an optional `semantic_scorer(a,b)->float` seam is exposed for a future embedding blend — the local sentence-transformer is a dependency but is intentionally NOT wired into the hot path/tests), aggregates the top matches' rates into a benchmark (count/min/max/avg/median + a suggested rate = median), and returns the matched records for traceability. The feedback loop is a first-class corpus insert (`source="feedback"`), and indexing a project snapshots its priced items into the corpus — so each completed tender enriches suggestions for the next. Root conventions hold: services take `db: AsyncSession`; enums/responses follow the v2 patterns; uploads are extension-validated + size-capped (Phase 9–11 lesson).

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + aiosqlite · Alembic (one additive migration) · openpyxl (rate-sheet import) · stdlib `statistics`/`difflib` (benchmark + matching) · pytest-asyncio + httpx ASGITransport.

**One additive migration is required** — a new `historical_prices` table (current head: `b3cf18d92e0a`). No existing table changes.

---

## Pre-flight (read, do not skip)

1. **Model registration is in THREE places.** A new model must be: (a) defined under `app/models/`, (b) imported + added to `__all__` in `app/models/__init__.py`, and (c) added to the model-module import list in `migrations/env.py` (lines 14-23) so Alembic autogenerate sees it. The app's lifespan and the test fixtures create tables via `Base.metadata.create_all`, so the model alone makes tests pass; the **migration** is for the real/upgraded DB.
2. **Migration style** (`migrations/versions/b3cf18d92e0a_boq_unit_nullable.py`): plain `revision`/`down_revision` strings, `from alembic import op`, `import sqlalchemy as sa`. The current head is `b3cf18d92e0a`; the new migration's `down_revision` must be `'b3cf18d92e0a'`.
3. **Reuse the matcher** — `from app.services.pricing.line_item_matcher import match_score, DEFAULT_THRESHOLD`. `match_score(a, b)` returns a 0–1 similarity; `DEFAULT_THRESHOLD = 0.45`. Do NOT reimplement similarity.
4. **Benchmark suggested rate = median** of the matched rates (robust to outliers); also return min/max/avg/count. Use `statistics.median`/`statistics.mean`.
5. **Don't suggest from the project's own items** — `suggest_for_project` must exclude corpus rows whose `source_project_id == project_id`. Because SQL `col != x` drops NULLs, use `or_(HistoricalPrice.source_project_id != project_id, HistoricalPrice.source_project_id.is_(None))` so imported (null-project) records stay in scope.
6. **`index_project` is idempotent per project** — delete existing rows with that `source_project_id` before re-inserting, so re-indexing never duplicates.
7. **Services take `db: AsyncSession`**; the matcher's `semantic_scorer` defaults to `None` (deterministic fuzzy). Uploads: validate `.xlsx` + cap size (mirror `app/api/suppliers.py` / Phase 11).
8. **Trade filter semantics:** when a `trade` is supplied, restrict the corpus to rows with that `trade_category` (keeps suggestions on-trade). When no trade is supplied, the whole corpus is scored.

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (must stay green; baseline = **197 passing**).

---

## File Structure

**Create:**
- `app/models/historical.py` — `HistoricalPrice` model.
- `migrations/versions/c7e1a2f3b4d5_historical_prices.py` — additive table migration.
- `app/schemas/historical.py` — request/response models.
- `app/services/historical/__init__.py`
- `app/services/historical/historical_service.py` — `HistoricalService` (add, import, index, suggest, suggest_for_project, feedback, list).
- `app/api/historical.py` — historical-learning router.
- `tests/historical/__init__.py`, `tests/historical/test_model.py`, `tests/historical/test_suggest.py`, `tests/historical/test_corpus.py`, `tests/historical/test_historical_api.py`

**Modify:**
- `app/models/__init__.py` — import + export `HistoricalPrice`.
- `migrations/env.py` — add `historical` to the model-module import list.
- `app/main.py` — register `historical_router`.

---

## Task 1: `HistoricalPrice` model + migration + registration

**Files:**
- Create: `app/models/historical.py`, `migrations/versions/c7e1a2f3b4d5_historical_prices.py`
- Modify: `app/models/__init__.py`, `migrations/env.py`
- Test: `tests/historical/__init__.py`, `tests/historical/test_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/historical/__init__.py` (empty file).

Create `tests/historical/test_model.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.historical import HistoricalPrice


async def test_historical_price_persists(db_session):
    rec = HistoricalPrice(
        description="Supply and install split AC unit",
        unit="no", rate=1200.0, currency="USD", trade_category="mep",
        source="import:rates2025.xlsx", recorded_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)
    assert rec.id is not None
    assert rec.created_at is not None  # TimestampMixin
    got = (await db_session.execute(
        select(HistoricalPrice).where(HistoricalPrice.trade_category == "mep")
    )).scalar_one()
    assert got.rate == 1200.0
    assert got.source_project_id is None  # nullable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_model.py -q`
Expected: FAIL — `ModuleNotFoundError: app.models.historical`.

- [ ] **Step 3: Implement the model**

Create `app/models/historical.py`:

```python
"""HistoricalPrice model — the corpus for price-benchmark learning."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HistoricalPrice(Base, TimestampMixin):
    """A single observed historical unit rate, used for benchmark suggestions.

    Sources: imported rate sheets, snapshots of a project's priced BOQ, or
    accepted/corrected user feedback. Decoupled from any one project so it can
    be reused across tenders.
    """

    __tablename__ = "historical_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    trade_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Provenance / traceability
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. import:/project:/feedback
    source_project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<HistoricalPrice {self.description[:40]} @ {self.rate}>"
```

- [ ] **Step 4: Register the model in `app/models/__init__.py`**

Add the import (keep alphabetical-ish, after `document`):

```python
from app.models.historical import HistoricalPrice
```

Add `"HistoricalPrice",` to the `__all__` list.

- [ ] **Step 5: Register the model module in `migrations/env.py`**

In the model-module import block (currently `audit, boq, document, email, package, project, supplier, user`), add `historical`:

```python
from app.models import (  # noqa: F401
    audit,
    boq,
    document,
    email,
    historical,
    package,
    project,
    supplier,
    user,
)
```

- [ ] **Step 6: Write the migration**

Create `migrations/versions/c7e1a2f3b4d5_historical_prices.py`:

```python
"""add historical_prices table

Revision ID: c7e1a2f3b4d5
Revises: b3cf18d92e0a
Create Date: 2026-06-10 00:00:00.000000

Net-new corpus table for Phase 13 historical-learning price suggestions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e1a2f3b4d5'
down_revision: Union[str, None] = 'b3cf18d92e0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historical_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("trade_category", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_project_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_historical_prices_id"), "historical_prices", ["id"])
    op.create_index(op.f("ix_historical_prices_trade_category"), "historical_prices", ["trade_category"])
    op.create_index(op.f("ix_historical_prices_source_project_id"), "historical_prices", ["source_project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_historical_prices_source_project_id"), table_name="historical_prices")
    op.drop_index(op.f("ix_historical_prices_trade_category"), table_name="historical_prices")
    op.drop_index(op.f("ix_historical_prices_id"), table_name="historical_prices")
    op.drop_table("historical_prices")
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_model.py -q`
Expected: PASS (1 test).

- [ ] **Step 8: Verify the migration chain is linear (single head)**

Run: `.venv/Scripts/python.exe -m alembic heads 2>&1 | cat`
Expected: a single head `c7e1a2f3b4d5` (one line). If `alembic` is not on PATH, run `.venv/Scripts/python.exe -m alembic -c alembic.ini heads`. (If alembic cannot connect to a DB that's fine — `heads` only reads the version scripts. If even that fails in this environment, skip this step; the model+create_all path is what tests exercise.)

- [ ] **Step 9: Commit**

```bash
git add app/models/historical.py app/models/__init__.py migrations/env.py migrations/versions/c7e1a2f3b4d5_historical_prices.py tests/historical/__init__.py tests/historical/test_model.py
git commit -m "feat(phase-13): HistoricalPrice corpus model + migration + registration"
```

---

## Task 2: Schemas + `HistoricalService.add` + `suggest` (core matching/benchmark)

**Files:**
- Create: `app/schemas/historical.py`, `app/services/historical/__init__.py`, `app/services/historical/historical_service.py`
- Test: `tests/historical/test_suggest.py`

- [ ] **Step 1: Write the schemas**

Create `app/schemas/historical.py`:

```python
"""Schemas for the historical-learning corpus, suggestions, import, feedback."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HistoricalPriceCreate(BaseModel):
    description: str
    rate: float
    unit: str | None = None
    currency: str | None = None
    trade_category: str | None = None
    description_ar: str | None = None
    source: str | None = None  # defaults to "manual" in the service


class HistoricalPriceResponse(BaseModel):
    id: int
    description: str
    unit: str | None = None
    rate: float
    currency: str | None = None
    trade_category: str | None = None
    source: str
    source_project_id: int | None = None
    recorded_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestionMatch(BaseModel):
    historical_id: int
    description: str
    unit: str | None = None
    rate: float
    currency: str | None = None
    source: str
    source_project_id: int | None = None
    similarity: float


class PriceBenchmark(BaseModel):
    count: int
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    median: float | None = None
    suggested_rate: float | None = None
    currency: str | None = None


class PriceSuggestion(BaseModel):
    query: str
    trade: str | None = None
    benchmark: PriceBenchmark
    matches: list[SuggestionMatch] = Field(default_factory=list)


class ItemSuggestion(BaseModel):
    boq_item_id: int
    line_number: str | None = None
    description: str
    suggestion: PriceSuggestion


class ProjectSuggestions(BaseModel):
    project_id: int
    suggestions: list[ItemSuggestion] = Field(default_factory=list)


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    total_errors: int


class IndexResult(BaseModel):
    project_id: int
    indexed: int


class FeedbackRequest(BaseModel):
    description: str
    accepted_rate: float
    unit: str | None = None
    currency: str | None = None
    trade_category: str | None = None
```

- [ ] **Step 2: Write the failing tests**

Create `tests/historical/test_suggest.py`:

```python
import pytest

from app.models.historical import HistoricalPrice
from app.services.historical.historical_service import HistoricalService


async def _seed_corpus(db):
    db.add_all([
        HistoricalPrice(description="Supply and install split AC unit", unit="no",
                        rate=1200.0, currency="USD", trade_category="mep", source="import:a"),
        HistoricalPrice(description="Split AC unit supply & installation", unit="no",
                        rate=1300.0, currency="USD", trade_category="mep", source="import:a"),
        HistoricalPrice(description="VRF outdoor condensing unit", unit="no",
                        rate=8000.0, currency="USD", trade_category="mep", source="import:a"),
        HistoricalPrice(description="Concrete grade C30 foundation", unit="m3",
                        rate=90.0, currency="USD", trade_category="civil", source="import:a"),
    ])
    await db.commit()


async def test_add_record(db_session):
    svc = HistoricalService()
    rec = await svc.add(db_session, description="Steel rebar", rate=750.0, trade_category="concrete")
    assert rec.id is not None
    assert rec.source == "manual"  # default source


async def test_suggest_aggregates_similar_rates(db_session):
    await _seed_corpus(db_session)
    out = await HistoricalService().suggest(
        db_session, "Split AC unit (supply & install)", trade="mep"
    )
    # the two AC records match; VRF is too different
    assert out["benchmark"]["count"] == 2
    assert out["benchmark"]["min"] == 1200.0
    assert out["benchmark"]["max"] == 1300.0
    assert out["benchmark"]["median"] == 1250.0
    assert out["benchmark"]["suggested_rate"] == 1250.0  # median
    assert out["benchmark"]["currency"] == "USD"
    descs = {m["description"] for m in out["matches"]}
    assert "VRF outdoor condensing unit" not in descs
    # every match carries traceability (id + similarity)
    assert all("historical_id" in m and m["similarity"] >= 0.45 for m in out["matches"])


async def test_suggest_trade_filter_excludes_other_trades(db_session):
    await _seed_corpus(db_session)
    out = await HistoricalService().suggest(db_session, "Concrete grade C30 foundation", trade="civil")
    assert out["benchmark"]["count"] == 1
    assert out["benchmark"]["suggested_rate"] == 90.0


async def test_suggest_no_match_returns_empty_benchmark(db_session):
    await _seed_corpus(db_session)
    out = await HistoricalService().suggest(db_session, "Curtain wall structural glazing", trade="mep")
    assert out["benchmark"]["count"] == 0
    assert out["benchmark"]["suggested_rate"] is None
    assert out["matches"] == []


async def test_suggest_respects_top_k(db_session):
    db_session.add_all([
        HistoricalPrice(description="cable tray 100mm", rate=float(10 + i),
                        trade_category="mep", source="import:b")
        for i in range(8)
    ])
    await db_session.commit()
    out = await HistoricalService().suggest(db_session, "cable tray 100mm", trade="mep", top_k=3)
    assert len(out["matches"]) == 3
    assert out["benchmark"]["count"] == 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_suggest.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.historical`.

- [ ] **Step 4: Implement the service core**

Create `app/services/historical/__init__.py` (empty file).

Create `app/services/historical/historical_service.py`:

```python
"""Historical price learning: corpus management + benchmark suggestions.

Matching reuses the deterministic Phase 11 fuzzy matcher; an optional
semantic_scorer(a, b) -> float can be injected to blend an embedding score
(the local sentence-transformer is a dependency but is intentionally not wired
into the default/tested path). Pure logic — no Gemini key.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, median

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical import HistoricalPrice
from app.services.pricing.line_item_matcher import DEFAULT_THRESHOLD, match_score

_DEFAULT_TOP_K = 5

# Editable corpus fields shared by add/import (keeps DRY).
_SETTABLE = (
    "description", "description_ar", "unit", "rate", "currency", "trade_category",
)


class HistoricalService:
    def __init__(self, semantic_scorer=None) -> None:
        self._semantic_scorer = semantic_scorer

    async def add(
        self,
        db: AsyncSession,
        *,
        description: str,
        rate: float,
        source: str = "manual",
        source_project_id: int | None = None,
        recorded_at: datetime | None = None,
        **fields,
    ) -> HistoricalPrice:
        rec = HistoricalPrice(
            description=description,
            rate=rate,
            source=source,
            source_project_id=source_project_id,
            recorded_at=recorded_at or datetime.now(timezone.utc),
            **{k: v for k, v in fields.items() if k in _SETTABLE},
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return rec

    async def list_records(
        self, db: AsyncSession, *, trade: str | None = None, limit: int = 200
    ) -> list[HistoricalPrice]:
        stmt = select(HistoricalPrice)
        if trade:
            stmt = stmt.where(HistoricalPrice.trade_category == trade)
        stmt = stmt.order_by(HistoricalPrice.id.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    def _benchmark(rates: list[float], currency: str | None) -> dict:
        if not rates:
            return {
                "count": 0, "min": None, "max": None, "avg": None,
                "median": None, "suggested_rate": None, "currency": currency,
            }
        med = round(median(rates), 2)
        return {
            "count": len(rates),
            "min": round(min(rates), 2),
            "max": round(max(rates), 2),
            "avg": round(mean(rates), 2),
            "median": med,
            "suggested_rate": med,
            "currency": currency,
        }

    async def suggest(
        self,
        db: AsyncSession,
        description: str,
        *,
        unit: str | None = None,
        trade: str | None = None,
        top_k: int = _DEFAULT_TOP_K,
        min_score: float = DEFAULT_THRESHOLD,
        exclude_project_id: int | None = None,
    ) -> dict:
        stmt = select(HistoricalPrice)
        if trade:
            stmt = stmt.where(HistoricalPrice.trade_category == trade)
        if exclude_project_id is not None:
            stmt = stmt.where(
                or_(
                    HistoricalPrice.source_project_id != exclude_project_id,
                    HistoricalPrice.source_project_id.is_(None),
                )
            )
        records = list((await db.execute(stmt)).scalars().all())

        scored: list[tuple[HistoricalPrice, float]] = []
        for rec in records:
            score = match_score(description, rec.description)
            if self._semantic_scorer is not None:
                score = max(score, float(self._semantic_scorer(description, rec.description)))
            if score >= min_score:
                scored.append((rec, round(score, 4)))
        scored.sort(key=lambda rs: rs[1], reverse=True)
        top = scored[:top_k]

        rates = [rec.rate for rec, _ in top]
        currency = next((rec.currency for rec, _ in top if rec.currency), None)
        matches = [
            {
                "historical_id": rec.id,
                "description": rec.description,
                "unit": rec.unit,
                "rate": rec.rate,
                "currency": rec.currency,
                "source": rec.source,
                "source_project_id": rec.source_project_id,
                "similarity": score,
            }
            for rec, score in top
        ]
        return {
            "query": description,
            "trade": trade,
            "benchmark": self._benchmark(rates, currency),
            "matches": matches,
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_suggest.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/historical.py app/services/historical/__init__.py app/services/historical/historical_service.py tests/historical/test_suggest.py
git commit -m "feat(phase-13): historical schemas + corpus add + benchmark suggest"
```

---

## Task 3: Corpus seeding — `import_excel`, `index_project`, `record_feedback`

**Files:**
- Modify: `app/services/historical/historical_service.py`
- Test: `tests/historical/test_corpus.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/historical/test_corpus.py`:

```python
import openpyxl
import pytest
from sqlalchemy import select

from app.models.boq import BOQItem
from app.models.historical import HistoricalPrice
from app.models.project import Project
from app.services.historical.historical_service import HistoricalService


def _make_rate_sheet(path, rows, headers=("Description", "Unit", "Rate", "Trade", "Currency")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return str(path)


async def test_import_excel_creates_records(db_session, tmp_path):
    f = _make_rate_sheet(tmp_path / "rates.xlsx", [
        ("Supply and install split AC unit", "no", 1200, "MEP", "USD"),
        ("Concrete grade C30", "m3", 90, "Civil", "USD"),
        ("", "no", 5, "MEP", "USD"),  # blank description -> skipped
        ("Missing rate", "no", "", "MEP", "USD"),  # no usable rate -> skipped
    ])
    svc = HistoricalService()
    res = await svc.import_excel(db_session, f)
    assert res["imported"] == 2
    assert res["skipped"] == 2
    recs = (await db_session.execute(select(HistoricalPrice))).scalars().all()
    assert {r.description for r in recs} == {"Supply and install split AC unit", "Concrete grade C30"}
    # trade normalized to a lowercase token (matches rules trade keys)
    assert {r.trade_category for r in recs} == {"mep", "civil"}
    assert all(r.source.startswith("import:") for r in recs)


async def test_index_project_snapshots_priced_items(db_session):
    project = Project(name="Metro Line 3")
    db_session.add(project)
    await db_session.flush()
    db_session.add_all([
        BOQItem(project_id=project.id, line_number="1", description="AC unit", unit="no",
                quantity=5, client_row_index=2, trade_category="mep",
                unit_rate=1200, total_price=6000, currency="USD"),
        BOQItem(project_id=project.id, line_number="2", description="Unpriced", unit="no",
                quantity=1, client_row_index=3, trade_category="mep"),  # no unit_rate -> skipped
        BOQItem(project_id=project.id, line_number="3", description="Excluded", unit="no",
                quantity=1, client_row_index=4, trade_category="mep",
                unit_rate=999, total_price=999, currency="USD", is_excluded=True),  # excluded
    ])
    await db_session.commit()
    svc = HistoricalService()
    res = await svc.index_project(db_session, project.id)
    assert res["indexed"] == 1  # only the one priced, non-excluded item
    rec = (await db_session.execute(
        select(HistoricalPrice).where(HistoricalPrice.source_project_id == project.id)
    )).scalar_one()
    assert rec.rate == 1200.0
    assert rec.source == "project:Metro Line 3"
    # re-indexing is idempotent (no duplicate rows)
    res2 = await svc.index_project(db_session, project.id)
    assert res2["indexed"] == 1
    count = len((await db_session.execute(
        select(HistoricalPrice).where(HistoricalPrice.source_project_id == project.id)
    )).scalars().all())
    assert count == 1


async def test_record_feedback_adds_corpus_record(db_session):
    svc = HistoricalService()
    rec = await svc.record_feedback(
        db_session, description="Split AC unit", accepted_rate=1275.0,
        unit="no", currency="USD", trade_category="mep",
    )
    assert rec.id is not None
    assert rec.rate == 1275.0
    assert rec.source == "feedback"
    # feedback immediately participates in suggestions
    out = await svc.suggest(db_session, "Split AC unit", trade="mep")
    assert out["benchmark"]["suggested_rate"] == 1275.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_corpus.py -q`
Expected: FAIL — `AttributeError: 'HistoricalService' object has no attribute 'import_excel'`.

- [ ] **Step 3: Implement the three methods**

Add the imports at the top of `app/services/historical/historical_service.py`:

```python
from pathlib import Path

from openpyxl import load_workbook

from app.models.boq import BOQItem
from app.models.project import Project
```

Add these methods to `HistoricalService`:

```python
    _COLUMN_CANDIDATES = {
        "description": ("description", "desc", "item", "item description", "particulars"),
        "unit": ("unit", "uom", "u/m"),
        "rate": ("rate", "unit rate", "unit price", "price", "amount"),
        "trade": ("trade", "trade category", "category", "division"),
        "currency": ("currency", "ccy"),
    }

    async def import_excel(
        self, db: AsyncSession, file_path: str, *, source: str | None = None
    ) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 - surface a clean message
            raise ValueError(f"Failed to read Excel file: {exc}") from exc
        rows = None
        src = source or f"import:{path.name}"
        try:
            ws = wb.active
            rows = ws.iter_rows(values_only=True)
            try:
                header = next(rows)
            except StopIteration:
                raise ValueError("Excel file is empty")
            normalized = [_norm_header(h) for h in header]
            col = {
                key: _find_col(normalized, cands)
                for key, cands in self._COLUMN_CANDIDATES.items()
            }
            if col["description"] is None or col["rate"] is None:
                raise ValueError("Required columns 'description' and 'rate' not found")

            imported = skipped = 0
            errors: list[str] = []
            for row_idx, row in enumerate(rows, start=2):
                try:
                    description = _cell(row, col["description"])
                    rate = _coerce_float(_cell(row, col["rate"]))
                    if not description or rate is None or rate <= 0:
                        skipped += 1
                        continue
                    trade = _cell(row, col["trade"])
                    db.add(
                        HistoricalPrice(
                            description=description,
                            unit=_cell(row, col["unit"]),
                            rate=rate,
                            currency=_cell(row, col["currency"]),
                            trade_category=_norm_trade(trade) if trade else None,
                            source=src,
                            recorded_at=datetime.now(timezone.utc),
                        )
                    )
                    imported += 1
                except Exception as exc:  # noqa: BLE001 - per-row resilience
                    errors.append(f"Row {row_idx}: {exc}")
            await db.commit()
        finally:
            if rows is not None:
                rows.close()
            wb.close()
        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],
            "total_errors": len(errors),
        }

    async def index_project(self, db: AsyncSession, project_id: int) -> dict:
        project = await db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        # Idempotent: clear this project's prior snapshot first.
        await db.execute(
            delete(HistoricalPrice).where(HistoricalPrice.source_project_id == project_id)
        )
        items = list(
            (
                await db.execute(
                    select(BOQItem).where(
                        BOQItem.project_id == project_id,
                        BOQItem.unit_rate.is_not(None),
                        BOQItem.is_excluded.is_(False),
                    )
                )
            ).scalars().all()
        )
        now = datetime.now(timezone.utc)
        for item in items:
            db.add(
                HistoricalPrice(
                    description=item.description,
                    description_ar=item.description_ar,
                    unit=item.unit,
                    rate=item.unit_rate,
                    currency=item.currency,
                    trade_category=item.trade_category,
                    source=f"project:{project.name}",
                    source_project_id=project_id,
                    recorded_at=now,
                )
            )
        await db.commit()
        return {"project_id": project_id, "indexed": len(items)}

    async def record_feedback(
        self,
        db: AsyncSession,
        *,
        description: str,
        accepted_rate: float,
        unit: str | None = None,
        currency: str | None = None,
        trade_category: str | None = None,
    ) -> HistoricalPrice:
        return await self.add(
            db,
            description=description,
            rate=accepted_rate,
            unit=unit,
            currency=currency,
            trade_category=trade_category,
            source="feedback",
        )
```

Add these module-level helpers at the bottom of the file (after the class):

```python
def _norm_header(value: object) -> str:
    return str(value or "").lower().strip()


def _find_col(normalized: list[str], candidates: tuple[str, ...]) -> int | None:
    for cand in candidates:
        if cand in normalized:
            return normalized.index(cand)
    return None


def _cell(row, idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    val = row[idx]
    if val is None:
        return None
    text = str(val).strip()
    return text or None


def _coerce_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _norm_trade(value: str) -> str:
    return value.strip().lower().replace(" ", "_")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_corpus.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/historical/historical_service.py tests/historical/test_corpus.py
git commit -m "feat(phase-13): corpus seeding — Excel import, project snapshot, feedback loop"
```

---

## Task 4: `suggest_for_project`

**Files:**
- Modify: `app/services/historical/historical_service.py`
- Test: `tests/historical/test_corpus.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/historical/test_corpus.py`:

```python
async def test_suggest_for_project_excludes_own_items(db_session):
    # Project A (the corpus source) and Project B (the one we suggest for).
    proj_a = Project(name="Past Tender")
    proj_b = Project(name="Current Tender")
    db_session.add_all([proj_a, proj_b])
    await db_session.flush()
    # Corpus: a record sourced from project A.
    db_session.add(HistoricalPrice(
        description="Supply and install split AC unit", unit="no", rate=1200.0,
        currency="USD", trade_category="mep", source="project:Past Tender",
        source_project_id=proj_a.id,
    ))
    # A record sourced from project B itself (must be excluded from B's suggestions).
    db_session.add(HistoricalPrice(
        description="Split AC unit supply and installation", unit="no", rate=9999.0,
        currency="USD", trade_category="mep", source="project:Current Tender",
        source_project_id=proj_b.id,
    ))
    # Unpriced item in project B that we want a suggestion for.
    db_session.add(BOQItem(
        project_id=proj_b.id, line_number="1", description="Split AC unit (supply & install)",
        unit="no", quantity=5, client_row_index=2, trade_category="mep",
    ))
    await db_session.commit()

    out = await HistoricalService().suggest_for_project(db_session, proj_b.id)
    assert len(out["suggestions"]) == 1
    sugg = out["suggestions"][0]["suggestion"]
    # only project A's 1200 is in scope; B's own 9999 is excluded
    assert sugg["benchmark"]["suggested_rate"] == 1200.0
    assert all(m["source_project_id"] != proj_b.id for m in sugg["matches"])


async def test_suggest_for_project_only_unpriced(db_session):
    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    db_session.add_all([
        BOQItem(project_id=project.id, line_number="1", description="Priced item",
                unit="no", quantity=1, client_row_index=2, trade_category="mep",
                unit_rate=500, total_price=500),
        BOQItem(project_id=project.id, line_number="2", description="Unpriced item",
                unit="no", quantity=1, client_row_index=3, trade_category="mep"),
    ])
    await db_session.commit()
    out = await HistoricalService().suggest_for_project(db_session, project.id, only_unpriced=True)
    assert len(out["suggestions"]) == 1
    assert out["suggestions"][0]["description"] == "Unpriced item"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_corpus.py -q -k suggest_for_project`
Expected: FAIL — `AttributeError: ... has no attribute 'suggest_for_project'`.

- [ ] **Step 3: Implement `suggest_for_project`**

Add this method to `HistoricalService`:

```python
    async def suggest_for_project(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        only_unpriced: bool = True,
        top_k: int = _DEFAULT_TOP_K,
        min_score: float = DEFAULT_THRESHOLD,
    ) -> dict:
        stmt = select(BOQItem).where(BOQItem.project_id == project_id)
        if only_unpriced:
            stmt = stmt.where(BOQItem.unit_rate.is_(None))
        stmt = stmt.order_by(BOQItem.client_row_index, BOQItem.id)
        items = list((await db.execute(stmt)).scalars().all())

        suggestions = []
        for item in items:
            suggestion = await self.suggest(
                db,
                item.description,
                unit=item.unit,
                trade=item.trade_category,
                top_k=top_k,
                min_score=min_score,
                exclude_project_id=project_id,
            )
            suggestions.append(
                {
                    "boq_item_id": item.id,
                    "line_number": item.line_number,
                    "description": item.description,
                    "suggestion": suggestion,
                }
            )
        return {"project_id": project_id, "suggestions": suggestions}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_corpus.py -q`
Expected: PASS (all 5 corpus tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/historical/historical_service.py tests/historical/test_corpus.py
git commit -m "feat(phase-13): per-project suggestions (excludes the project's own corpus rows)"
```

---

## Task 5: Historical-learning API router

**Files:**
- Create: `app/api/historical.py`
- Modify: `app/main.py`
- Test: `tests/historical/test_historical_api.py`

Endpoints:
- `POST  /api/historical` — add one corpus record.
- `GET   /api/historical?trade=` — list corpus records.
- `POST  /api/historical/import` — upload an `.xlsx` rate sheet (size-capped).
- `POST  /api/historical/feedback` — record an accepted/corrected rate.
- `GET   /api/historical/suggest?description=&unit=&trade=&top_k=` — ad-hoc benchmark suggestion.
- `POST  /api/projects/{pid}/historical/index` — snapshot a project's priced BOQ into the corpus.
- `GET   /api/projects/{pid}/historical/suggestions?only_unpriced=` — suggestions for the project's items.

- [ ] **Step 1: Write the failing tests**

Create `tests/historical/test_historical_api.py`:

```python
import io

import httpx
import openpyxl
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def hist_client():
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
        project = Project(name="Current")
        seed.add(project)
        await seed.flush()
        seed.add(BOQItem(project_id=project.id, line_number="1",
                         description="Split AC unit supply and install", unit="no",
                         quantity=5, client_row_index=2, trade_category="mep"))
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


async def test_add_list_and_suggest(hist_client):
    client, _ = hist_client
    async with client as c:
        a = await c.post("/api/historical", json={
            "description": "Supply and install split AC unit", "rate": 1200,
            "unit": "no", "currency": "USD", "trade_category": "mep"})
        assert a.status_code == 201, a.text
        await c.post("/api/historical", json={
            "description": "Split AC unit supply & installation", "rate": 1300,
            "trade_category": "mep", "currency": "USD"})

        lst = await c.get("/api/historical", params={"trade": "mep"})
        assert lst.status_code == 200 and len(lst.json()) == 2

        sug = await c.get("/api/historical/suggest",
                          params={"description": "Split AC unit (supply & install)", "trade": "mep"})
        assert sug.status_code == 200
        assert sug.json()["benchmark"]["suggested_rate"] == 1250.0


async def test_import_endpoint(hist_client):
    client, _ = hist_client
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Description", "Unit", "Rate", "Trade", "Currency"])
    ws.append(["Concrete C30", "m3", 90, "Civil", "USD"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    async with client as c:
        r = await c.post("/api/historical/import",
                         files={"file": ("rates.xlsx", buf.getvalue(),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 200, r.text
        assert r.json()["imported"] == 1


async def test_import_rejects_non_xlsx(hist_client):
    client, _ = hist_client
    async with client as c:
        r = await c.post("/api/historical/import",
                         files={"file": ("x.txt", b"not a spreadsheet", "text/plain")})
    assert r.status_code == 400


async def test_feedback_then_suggest(hist_client):
    client, _ = hist_client
    async with client as c:
        fb = await c.post("/api/historical/feedback", json={
            "description": "Split AC unit", "accepted_rate": 1275, "trade_category": "mep"})
        assert fb.status_code == 201
        sug = await c.get("/api/historical/suggest",
                          params={"description": "Split AC unit", "trade": "mep"})
        assert sug.json()["benchmark"]["suggested_rate"] == 1275.0


async def test_index_then_project_suggestions(hist_client):
    client, pid = hist_client
    # Index a SEPARATE past project so the current project gets a suggestion.
    async with client as c:
        # seed a past project with a priced item via the add endpoint (corpus directly)
        await c.post("/api/historical", json={
            "description": "Split AC unit supply and install", "rate": 1200,
            "trade_category": "mep", "currency": "USD"})
        sugg = await c.get(f"/api/projects/{pid}/historical/suggestions",
                           params={"only_unpriced": True})
        assert sugg.status_code == 200
        body = sugg.json()
        assert body["project_id"] == pid
        assert len(body["suggestions"]) == 1
        assert body["suggestions"][0]["suggestion"]["benchmark"]["suggested_rate"] == 1200.0

        idx = await c.post(f"/api/projects/{pid}/historical/index")
        assert idx.status_code == 200
        assert idx.json()["indexed"] == 0  # current project has no priced items


async def test_suggestions_404_missing_project(hist_client):
    client, _ = hist_client
    async with client as c:
        r = await c.get("/api/projects/999999/historical/suggestions")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_historical_api.py -q`
Expected: FAIL — router not registered / 404s.

- [ ] **Step 3: Implement the router**

Create `app/api/historical.py`:

```python
"""Historical-learning API: corpus management, Excel import, project snapshot,
benchmark suggestions, and the correction-feedback loop."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.historical import (
    FeedbackRequest,
    HistoricalPriceCreate,
    HistoricalPriceResponse,
    ImportResult,
    IndexResult,
    PriceSuggestion,
    ProjectSuggestions,
)
from app.services.historical.historical_service import HistoricalService

router = APIRouter(tags=["historical"])

# Cap inbound rate-sheet uploads (consistent with suppliers/pricing).
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_EXT = {".xlsx"}


@router.post("/historical", response_model=HistoricalPriceResponse, status_code=201)
async def add_record(
    payload: HistoricalPriceCreate, db: AsyncSession = Depends(get_db)
) -> HistoricalPriceResponse:
    data = payload.model_dump(exclude_unset=True)
    source = data.pop("source", None) or "manual"
    rec = await HistoricalService().add(
        db,
        description=data.pop("description"),
        rate=data.pop("rate"),
        source=source,
        **data,
    )
    return HistoricalPriceResponse.model_validate(rec)


@router.get("/historical", response_model=list[HistoricalPriceResponse])
async def list_records(
    trade: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[HistoricalPriceResponse]:
    recs = await HistoricalService().list_records(db, trade=trade)
    return [HistoricalPriceResponse.model_validate(r) for r in recs]


@router.post("/historical/import", response_model=ImportResult)
async def import_rate_sheet(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file type; upload .xlsx")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                tmp.close()
                Path(tmp_path).unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Upload exceeds the maximum allowed size")
            tmp.write(chunk)
    try:
        result = await HistoricalService().import_excel(db, tmp_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return ImportResult(**result)


@router.post("/historical/feedback", response_model=HistoricalPriceResponse, status_code=201)
async def record_feedback(
    payload: FeedbackRequest, db: AsyncSession = Depends(get_db)
) -> HistoricalPriceResponse:
    rec = await HistoricalService().record_feedback(
        db,
        description=payload.description,
        accepted_rate=payload.accepted_rate,
        unit=payload.unit,
        currency=payload.currency,
        trade_category=payload.trade_category,
    )
    return HistoricalPriceResponse.model_validate(rec)


@router.get("/historical/suggest", response_model=PriceSuggestion)
async def suggest(
    description: str = Query(..., min_length=1),
    unit: str | None = Query(default=None),
    trade: str | None = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> PriceSuggestion:
    out = await HistoricalService().suggest(
        db, description, unit=unit, trade=trade, top_k=top_k
    )
    return PriceSuggestion(**out)


@router.post("/projects/{project_id}/historical/index", response_model=IndexResult)
async def index_project(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> IndexResult:
    try:
        result = await HistoricalService().index_project(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IndexResult(**result)


@router.get(
    "/projects/{project_id}/historical/suggestions", response_model=ProjectSuggestions
)
async def project_suggestions(
    project_id: int,
    only_unpriced: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> ProjectSuggestions:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    out = await HistoricalService().suggest_for_project(
        db, project_id, only_unpriced=only_unpriced
    )
    return ProjectSuggestions(**out)
```

- [ ] **Step 4: Register the router in `app/main.py`**

Add the import (alphabetical block is fine):

```python
from app.api.historical import router as historical_router
```

Add the registration after the indirects router:

```python
app.include_router(historical_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/historical/test_historical_api.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/historical.py app/main.py tests/historical/test_historical_api.py
git commit -m "feat(phase-13): historical-learning API — corpus, import, index, suggest, feedback"
```

---

## Task 6: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, zero failures, no new skips. Baseline was 197; this phase adds 1 (model) + 5 (suggest) + 5 (corpus) + 6 (API) = **17** → **214 passing** (±a couple). Hard requirement: zero failures.

- [ ] **Step 2: Smoke-check routes register**

Run:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'historical' in p))"
```
Expected:
```
/api/historical
/api/historical/feedback
/api/historical/import
/api/historical/suggest
/api/projects/{project_id}/historical/index
/api/projects/{project_id}/historical/suggestions
```

- [ ] **Step 3: Final commit (if anything uncommitted)**

```bash
git add -A
git commit -m "test(phase-13): full suite green — historical learning corpus + suggestions"
```

---

## Spec Coverage Self-Review

| Phase 13 spec requirement (spec §6 cap 11) | Task |
|---|---|
| Index historical sheets (corpus) | 1 (model), 3 (Excel import + project snapshot) |
| Suggest prices / benchmarks | 2 (suggest + benchmark), 4 (per-project) |
| Traceability of suggestions | 2 (`matches` carry historical_id + source + similarity) |
| Correction feedback loop | 3 (`record_feedback` → corpus), 5 (endpoint) |
| API surfacing | 5 |
| Fully configurable / no hardcoded market | n/a (rates are data; no market constants introduced) |
| Works without a Gemini key | all (deterministic fuzzy matching) |
| Root conventions (db param, migration registered 3 places, capped uploads) | 1, 3, 5 |

**Scope note on "semantic" matching:** as in Phase 11, suggestions use the deterministic fuzzy matcher by default, with an injectable `semantic_scorer` seam for a future embedding blend (the local sentence-transformer is a dependency but is deliberately kept out of the default/test path to keep tests fast and offline). This is a documented scope choice, not an omission.

**Deferred / out of scope:** auto-applying suggestions into BOQ prices (the user applies a suggested rate via the existing Phase 11 `PATCH /api/boq-items/{id}/price`, and that priced item is then captured into the corpus on the next `index`); client deliverables/dashboard (Phase 14); React UI (Phase 6C); time-decay / recency weighting of historical rates (all records weigh equally — a later phase can weight by `recorded_at`).
