# Phase 9 — Suppliers + SMTP Draft-Only RFQ Email — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global supplier database (CRUD + Excel import/export) and a draft-only, bilingual (en/ar) RFQ email system that creates reviewable email drafts per package×supplier, logs them, and sends only on an explicit, separate user action via SMTP.

**Architecture:** Mirror the existing root-app conventions exactly — services take an injected `db: AsyncSession` parameter (NOT `get_db_context`), routers inject `db = Depends(get_db)`, enums are stored as `.value` strings, nested responses are built from explicitly-loaded children (never lazy relationship loads → avoid `MissingGreenlet`). Suppliers are **global** (single-user; `organization_id` stays `NULL`, auth deferred to Phase 15). The SMTP transport is an **injectable boundary** (`SMTPSender`) so draft/send logic is testable without a real server — same pattern as `DocumentLinker(search_service=…)`. Email content/policy (from-address, reply-to, subject formats, default language, attachment size cap) comes from the configurable **rules** system; SMTP secrets come from **settings/.env**. Every email is created as a `DRAFT`; nothing is ever auto-sent.

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + aiosqlite · openpyxl (Excel — **no pandas**, it is not a dependency) · Jinja2 (email body rendering — already a dependency) · stdlib `smtplib`/`email.mime` (SMTP) · pytest-asyncio + httpx ASGITransport (tests).

**No database migration is required** — the `suppliers`, `supplier_offers`, and `email_logs` tables already exist (created by migration `a2bb5607f46c`). This phase adds no columns.

---

## Pre-flight (read, do not skip)

The implementer MUST internalize these codebase facts before writing code. They are the difference between code that runs and code that silently breaks on SQLite/async:

1. **`EmailLog` Python attribute names differ from column names.** The model maps `to` → column `to_addresses`, `cc` → `cc_addresses`, `bcc` → `bcc_addresses` (see `app/models/email.py:41-43`). Construct with `EmailLog(to=[...], cc=..., bcc=...)`, **never** `to_addresses=...`. Pydantic `from_attributes` reads the Python attr names (`to`/`cc`/`bcc`).
2. **Enums are stored as strings.** `EmailLog.email_type`/`status` and `SupplierOffer.status` are `String` columns. Always assign `EmailType.RFQ.value` / `EmailStatus.DRAFT.value`, and compare against `.value`. (See `app/models/email.py:37-38`, root convention.)
3. **Do NOT use SQLAlchemy JSON `.contains()` for trade matching.** The salvage code used `Supplier.trade_categories.contains([trade])`; that targeted Postgres and does **not** work on SQLite/aiosqlite. Filter trades **in Python** after a base query (supplier counts are small). This also keeps tests (in-memory SQLite) honest.
4. **`Project` has no `code` column** (only `id`, `name`, `description`; see `app/models/project.py`). The rules subject format uses `{project_code}` — derive it as `project.name` (fallback). Always pass *all* placeholder keys (`project_code`, `package_name`, `package_code`, `supplier_name`) to `str.format` so a format string can never raise `KeyError`.
5. **Services take `db` as a parameter.** Follow `PackagingService().generate(db, project_id)` / `DocumentLinker().link_all(db, project_id)`. Do not open new sessions inside services.
6. **Build nested API responses from explicitly-loaded children.** Lazy-loading a relationship inside an async request raises `MissingGreenlet`. Load with `select(...)` then map to schemas (see `app/api/packaging.py:113-139`).
7. **Tests** live under `tests/<area>/` with `__init__.py`; unit tests use the `db_session` fixture (`tests/conftest.py`); API tests build their own in-memory engine + `app.dependency_overrides[get_db]` + `httpx.AsyncClient(transport=ASGITransport(app=app))` (copy the fixture shape from `tests/packaging/test_packaging_api.py`). `pytest.ini`/config already enables asyncio auto mode (58 tests pass with bare `async def test_*`).

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (must stay green; baseline = 58 passing).

---

## File Structure

**Create:**
- `app/schemas/supplier.py` — supplier request/response models.
- `app/schemas/email.py` — RFQ/email request/response models.
- `app/services/supplier/__init__.py`
- `app/services/supplier/supplier_service.py` — `SupplierService` (CRUD, search, trade match, blacklist, Excel import/export).
- `app/services/email/__init__.py`
- `app/services/email/templates.py` — bilingual (en/ar) Jinja2 body templates + `render_body` + `html_to_text`.
- `app/services/email/smtp_sender.py` — `SMTPSender` injectable transport + `SendError`.
- `app/services/email/rfq_service.py` — `RFQService` (suggested suppliers, create RFQ drafts, list/get/update draft, send).
- `app/api/suppliers.py` — `/api/suppliers` router (global CRUD + import/export).
- `app/api/emails.py` — RFQ creation (under project/package), suggested-suppliers, email log list/get/update/send.
- `tests/suppliers/__init__.py`, `tests/suppliers/test_supplier_service.py`, `tests/suppliers/test_supplier_excel.py`, `tests/suppliers/test_suppliers_api.py`
- `tests/email/__init__.py`, `tests/email/test_templates.py`, `tests/email/test_smtp_sender.py`, `tests/email/test_rfq_service.py`, `tests/email/test_emails_api.py`

**Modify:**
- `app/config.py` — add SMTP/email-identity settings (`BIDOPS_`-prefixed).
- `app/main.py` — register `suppliers_router` and `emails_router`.

---

## Task 1: SMTP & email-identity settings

**Files:**
- Modify: `app/config.py`
- Test: `tests/email/test_smtp_sender.py` (created in Task 8 — Task 1 just adds the fields)

These are transport secrets/identity, distinct from the rules `email` section (content/policy). Empty defaults → SMTP simply "not configured" and `/send` degrades gracefully (503), while draft creation always works.

- [ ] **Step 1: Add settings fields**

In `app/config.py`, inside `class Settings`, after the NLI block (around line 32) and before the confidence thresholds, add:

```python
    # SMTP transport for outbound email (Phase 9). Empty host/user => "not
    # configured": drafts still work, but POST /send returns 503. Set these in
    # .env with the BIDOPS_ prefix (e.g. BIDOPS_SMTP_HOST=...) to enable sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Sender identity (Phase 9). from_address resolution order at send time:
    # rules.email.from_address -> settings.email_from -> settings.smtp_user.
    email_from: str = ""
    email_from_name: str = "BidOps AI"
    company_name: str = "BidOps"
```

- [ ] **Step 2: Verify settings import cleanly**

Run: `.venv/Scripts/python.exe -c "from app.config import get_settings; s=get_settings(); print(s.smtp_port, repr(s.email_from_name))"`
Expected: `587 'BidOps AI'`

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat(phase-9): add SMTP transport + sender-identity settings"
```

---

## Task 2: Supplier schemas

**Files:**
- Create: `app/schemas/supplier.py`
- Test: covered indirectly by Task 3/5 tests (schemas are plain data; no standalone test needed).

- [ ] **Step 1: Write the schemas**

Create `app/schemas/supplier.py`:

```python
"""Schemas for supplier CRUD, search, and Excel import."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str
    emails: list[str] = Field(default_factory=list)
    trade_categories: list[str] = Field(default_factory=list)
    name_ar: str | None = None
    code: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    region: str | None = None
    country: str | None = None
    rating: float | None = None
    preferred_language: str | None = None
    preferred_format: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    """All fields optional; only provided fields are updated."""

    name: str | None = None
    emails: list[str] | None = None
    trade_categories: list[str] | None = None
    name_ar: str | None = None
    code: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    region: str | None = None
    country: str | None = None
    rating: float | None = None
    preferred_language: str | None = None
    preferred_format: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    name_ar: str | None = None
    code: str | None = None
    emails: list[str] = Field(default_factory=list)
    phone: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    trade_categories: list[str] = Field(default_factory=list)
    region: str | None = None
    country: str | None = None
    rating: float | None = None
    preferred_language: str | None = None
    is_active: bool = True
    is_blacklisted: bool = False
    total_rfqs_sent: int = 0
    total_offers_received: int = 0

    model_config = {"from_attributes": True}


class BlacklistRequest(BaseModel):
    reason: str


class SupplierImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    total_errors: int
```

- [ ] **Step 2: Verify import**

Run: `.venv/Scripts/python.exe -c "from app.schemas.supplier import SupplierCreate, SupplierResponse; print(SupplierCreate(name='X').trade_categories)"`
Expected: `[]`

- [ ] **Step 3: Commit**

```bash
git add app/schemas/supplier.py
git commit -m "feat(phase-9): supplier request/response schemas"
```

---

## Task 3: SupplierService — CRUD, search, trade match, blacklist

**Files:**
- Create: `app/services/supplier/__init__.py`, `app/services/supplier/supplier_service.py`
- Test: `tests/suppliers/__init__.py`, `tests/suppliers/test_supplier_service.py`

`organization_id` stays `None` (single-user/global). Trade filtering is done **in Python** (no JSON `.contains`).

- [ ] **Step 1: Write the failing tests**

Create `tests/suppliers/__init__.py` (empty file).

Create `tests/suppliers/test_supplier_service.py`:

```python
import pytest

from app.models.base import EmailStatus, EmailType
from app.models.email import EmailLog
from app.services.supplier.supplier_service import SupplierService


async def test_create_assigns_code_and_persists(db_session):
    svc = SupplierService()
    sup = await svc.create(
        db_session, name="Acme Steel", emails=["sales@acme.test"],
        trade_categories=["structural_steel"],
    )
    assert sup.id is not None
    assert sup.code == "SUP-0001"
    assert sup.organization_id is None
    assert sup.is_active is True


async def test_create_respects_explicit_code(db_session):
    svc = SupplierService()
    sup = await svc.create(db_session, name="X", emails=[], trade_categories=[], code="V-99")
    assert sup.code == "V-99"


async def test_codes_increment(db_session):
    svc = SupplierService()
    a = await svc.create(db_session, name="A", emails=[], trade_categories=[])
    b = await svc.create(db_session, name="B", emails=[], trade_categories=[])
    assert (a.code, b.code) == ("SUP-0001", "SUP-0002")


async def test_get_and_update(db_session):
    svc = SupplierService()
    sup = await svc.create(db_session, name="A", emails=[], trade_categories=[])
    got = await svc.get(db_session, sup.id)
    assert got.name == "A"
    updated = await svc.update(db_session, sup.id, name="A2", rating=4.5)
    assert updated.name == "A2"
    assert updated.rating == 4.5
    assert await svc.update(db_session, 999999, name="nope") is None


async def test_list_filters_query_and_active(db_session):
    svc = SupplierService()
    await svc.create(db_session, name="Concrete Co", emails=[], trade_categories=["concrete"])
    inactive = await svc.create(db_session, name="Old Co", emails=[], trade_categories=["concrete"])
    await svc.update(db_session, inactive.id, is_active=False)
    # default lists active only
    names = {s.name for s in await svc.list_suppliers(db_session)}
    assert names == {"Concrete Co"}
    # query match by name (case-insensitive)
    assert len(await svc.list_suppliers(db_session, query="concrete")) == 1
    # include inactive
    assert len(await svc.list_suppliers(db_session, is_active=None)) == 2


async def test_list_filters_trade_in_python(db_session):
    svc = SupplierService()
    await svc.create(db_session, name="Steelco", emails=[], trade_categories=["structural_steel", "mep"])
    await svc.create(db_session, name="Concrete Co", emails=[], trade_categories=["concrete"])
    res = await svc.list_suppliers(db_session, trade="mep")
    assert [s.name for s in res] == ["Steelco"]


async def test_suppliers_for_trade_excludes_blacklisted_and_orders_by_rating(db_session):
    svc = SupplierService()
    low = await svc.create(db_session, name="Low", emails=[], trade_categories=["mep"], rating=2.0)
    high = await svc.create(db_session, name="High", emails=[], trade_categories=["mep"], rating=5.0)
    bad = await svc.create(db_session, name="Bad", emails=[], trade_categories=["mep"], rating=5.0)
    await svc.blacklist(db_session, bad.id, reason="fraud")
    res = await svc.suppliers_for_trade(db_session, "mep")
    assert [s.name for s in res] == ["High", "Low"]


async def test_blacklist_deactivates(db_session):
    svc = SupplierService()
    sup = await svc.create(db_session, name="A", emails=[], trade_categories=[])
    out = await svc.blacklist(db_session, sup.id, reason="late delivery")
    assert out.is_blacklisted is True
    assert out.is_active is False
    assert out.blacklist_reason == "late delivery"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/suppliers/test_supplier_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.supplier`.

- [ ] **Step 3: Implement the service**

Create `app/services/supplier/__init__.py` (empty file).

Create `app/services/supplier/supplier_service.py`:

```python
"""Supplier management: CRUD, search, trade matching, blacklist, Excel I/O.

Single-user/global for now (organization_id stays NULL; auth is Phase 15).
Trade-category matching is done in Python — SQLAlchemy JSON .contains() does
not work on SQLite/aiosqlite.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier

# Editable supplier fields shared by create/update (keeps DRY).
_SETTABLE = (
    "name", "name_ar", "code", "emails", "trade_categories", "phone", "fax",
    "address", "website", "contact_name", "contact_email", "contact_phone",
    "region", "country", "rating", "preferred_language", "preferred_format",
    "notes",
)


class SupplierService:
    async def _next_code(self, db: AsyncSession) -> str:
        count = (await db.execute(select(func.count(Supplier.id)))).scalar() or 0
        return f"SUP-{count + 1:04d}"

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        emails: list[str],
        trade_categories: list[str],
        **fields,
    ) -> Supplier:
        code = fields.pop("code", None) or await self._next_code(db)
        supplier = Supplier(
            organization_id=None,
            name=name,
            code=code,
            emails=emails or [],
            trade_categories=trade_categories or [],
            **{k: v for k, v in fields.items() if k in _SETTABLE},
        )
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    async def get(self, db: AsyncSession, supplier_id: int) -> Supplier | None:
        return await db.get(Supplier, supplier_id)

    async def update(
        self, db: AsyncSession, supplier_id: int, **fields
    ) -> Supplier | None:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            return None
        for key, value in fields.items():
            if value is None:
                continue
            if key in _SETTABLE or key == "is_active":
                setattr(supplier, key, value)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    async def list_suppliers(
        self,
        db: AsyncSession,
        *,
        query: str | None = None,
        trade: str | None = None,
        region: str | None = None,
        is_active: bool | None = True,
        min_rating: float | None = None,
    ) -> list[Supplier]:
        stmt = select(Supplier)
        if query:
            term = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Supplier.name.ilike(term),
                    Supplier.code.ilike(term),
                    Supplier.contact_name.ilike(term),
                )
            )
        if region:
            stmt = stmt.where(Supplier.region == region)
        if is_active is not None:
            stmt = stmt.where(Supplier.is_active == is_active)
        if min_rating is not None:
            stmt = stmt.where(Supplier.rating >= min_rating)
        stmt = stmt.order_by(Supplier.name)
        rows = list((await db.execute(stmt)).scalars().all())
        # Trade filter in Python (JSON .contains is not portable to SQLite).
        if trade:
            rows = [s for s in rows if trade in (s.trade_categories or [])]
        return rows

    async def suppliers_for_trade(
        self, db: AsyncSession, trade: str, limit: int = 50
    ) -> list[Supplier]:
        stmt = (
            select(Supplier)
            .where(Supplier.is_active.is_(True), Supplier.is_blacklisted.is_(False))
            .order_by(Supplier.rating.desc().nullslast(), Supplier.name)
        )
        rows = [
            s
            for s in (await db.execute(stmt)).scalars().all()
            if trade in (s.trade_categories or [])
        ]
        return rows[:limit]

    async def blacklist(
        self, db: AsyncSession, supplier_id: int, reason: str
    ) -> Supplier | None:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            return None
        supplier.is_blacklisted = True
        supplier.is_active = False
        supplier.blacklist_reason = reason
        await db.commit()
        await db.refresh(supplier)
        return supplier
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/suppliers/test_supplier_service.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/supplier/ tests/suppliers/__init__.py tests/suppliers/test_supplier_service.py
git commit -m "feat(phase-9): SupplierService CRUD/search/trade-match/blacklist"
```

---

## Task 4: Supplier Excel import/export (openpyxl)

**Files:**
- Modify: `app/services/supplier/supplier_service.py`
- Test: `tests/suppliers/test_supplier_excel.py`

Use **openpyxl** (no pandas). Import reads a header row, maps columns by candidate names, parses multi-value email/trade cells, normalizes trades to lowercase rules-key tokens (`structural steel` → `structural_steel`).

- [ ] **Step 1: Write the failing tests**

Create `tests/suppliers/test_supplier_excel.py`:

```python
import openpyxl
import pytest
from sqlalchemy import select

from app.models.supplier import Supplier
from app.services.supplier.supplier_service import SupplierService


def _make_xlsx(path, rows, headers=("Name", "Email", "Trade", "Phone", "Region")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return str(path)


async def test_import_creates_suppliers_and_parses_multivalue(db_session, tmp_path):
    f = _make_xlsx(
        tmp_path / "sup.xlsx",
        [
            ("Acme Steel", "a@x.test; b@x.test", "Structural Steel, MEP", "123", "North"),
            ("Concrete Co", "c@x.test", "Concrete", "456", "South"),
        ],
    )
    svc = SupplierService()
    res = await svc.import_excel(db_session, f)
    assert res["imported"] == 2
    assert res["skipped"] == 0
    acme = (await db_session.execute(
        select(Supplier).where(Supplier.name == "Acme Steel")
    )).scalar_one()
    assert acme.emails == ["a@x.test", "b@x.test"]
    assert acme.trade_categories == ["structural_steel", "mep"]
    assert acme.code == "SUP-0001"


async def test_import_skips_blank_names(db_session, tmp_path):
    f = _make_xlsx(tmp_path / "s.xlsx", [("", "x@x.test", "concrete", "", ""), ("Real", "r@x.test", "mep", "", "")])
    svc = SupplierService()
    res = await svc.import_excel(db_session, f)
    assert res["imported"] == 1
    assert res["skipped"] == 1


async def test_import_update_existing(db_session, tmp_path):
    svc = SupplierService()
    await svc.create(db_session, name="Acme Steel", emails=["old@x.test"], trade_categories=["concrete"])
    f = _make_xlsx(tmp_path / "s.xlsx", [("Acme Steel", "new@x.test", "MEP", "999", "East")])
    res = await svc.import_excel(db_session, f, update_existing=True)
    assert res["updated"] == 1
    assert res["imported"] == 0
    acme = (await db_session.execute(select(Supplier).where(Supplier.name == "Acme Steel"))).scalar_one()
    assert acme.emails == ["new@x.test"]
    assert acme.trade_categories == ["mep"]


async def test_import_missing_name_column_raises(db_session, tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Company", "Email"]); ws.append(["X", "x@x.test"])
    p = tmp_path / "bad.xlsx"; wb.save(p)
    svc = SupplierService()
    with pytest.raises(ValueError):
        await svc.import_excel(db_session, str(p))


async def test_export_roundtrips(db_session, tmp_path):
    svc = SupplierService()
    await svc.create(db_session, name="Acme", emails=["a@x.test"], trade_categories=["mep"], region="North", rating=4.0)
    out = await svc.export_excel(db_session, str(tmp_path / "out.xlsx"))
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    header = [c.value for c in ws[1]]
    assert header[0] == "Code" and "Name" in header
    assert ws.cell(row=2, column=2).value == "Acme"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/suppliers/test_supplier_excel.py -q`
Expected: FAIL — `AttributeError: 'SupplierService' object has no attribute 'import_excel'`.

- [ ] **Step 3: Implement import/export**

Append to `app/services/supplier/supplier_service.py` — first add imports at the top of the file:

```python
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
```

Then add these methods to `SupplierService` and the module-level helpers below the class:

```python
    _COLUMN_CANDIDATES = {
        "name": ("name", "supplier_name", "company", "vendor", "supplier"),
        "email": ("email", "emails", "email_address", "e-mail", "e_mail"),
        "trade": ("trade", "trades", "trade_category", "category", "specialization"),
        "phone": ("phone", "telephone", "tel", "mobile"),
        "contact": ("contact", "contact_name", "contact_person", "person"),
        "region": ("region", "area", "location"),
        "country": ("country",),
        "address": ("address", "full_address"),
        "website": ("website", "web", "url"),
    }

    async def import_excel(
        self, db: AsyncSession, file_path: str, update_existing: bool = False
    ) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 - surface a clean message
            raise ValueError(f"Failed to read Excel file: {exc}") from exc
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise ValueError("Excel file is empty")

        normalized = [_norm_header(h) for h in header]
        col = {
            key: _find_col(normalized, candidates)
            for key, candidates in self._COLUMN_CANDIDATES.items()
        }
        if col["name"] is None:
            raise ValueError("Required column 'name' not found")

        imported = updated = skipped = 0
        errors: list[str] = []
        # Capture the supplier count ONCE up front. Calling _count() inside the
        # loop would trigger autoflush of pending db.add()s and double-count,
        # producing gapped codes. base + imported + 1 stays correct & gap-free.
        base_count = await self._count(db)

        for row_idx, row in enumerate(rows, start=2):
            try:
                name = _cell(row, col["name"])
                if not name:
                    skipped += 1
                    continue
                emails = _split_multi(_cell(row, col["email"]), at_only=True)
                trades = [
                    _norm_trade(t)
                    for t in _split_multi(_cell(row, col["trade"]))
                    if t
                ]
                existing = (
                    await db.execute(select(Supplier).where(Supplier.name == name))
                ).scalar_one_or_none()
                if existing is not None:
                    if not update_existing:
                        skipped += 1
                        continue
                    if emails:
                        existing.emails = emails
                    if trades:
                        existing.trade_categories = trades
                    for fld, idx in (("phone", col["phone"]), ("contact_name", col["contact"]),
                                     ("region", col["region"]), ("country", col["country"]),
                                     ("address", col["address"]), ("website", col["website"])):
                        val = _cell(row, idx)
                        if val:
                            setattr(existing, fld, val)
                    updated += 1
                    continue

                supplier = Supplier(
                    organization_id=None,
                    name=name,
                    code=f"SUP-{base_count + imported + 1:04d}",
                    emails=emails,
                    trade_categories=trades,
                    phone=_cell(row, col["phone"]),
                    contact_name=_cell(row, col["contact"]),
                    region=_cell(row, col["region"]),
                    country=_cell(row, col["country"]),
                    address=_cell(row, col["address"]),
                    website=_cell(row, col["website"]),
                )
                db.add(supplier)
                imported += 1
            except Exception as exc:  # noqa: BLE001 - per-row resilience
                errors.append(f"Row {row_idx}: {exc}")

        await db.commit()
        wb.close()
        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "errors": errors[:10],
            "total_errors": len(errors),
        }

    async def _count(self, db: AsyncSession) -> int:
        return (await db.execute(select(func.count(Supplier.id)))).scalar() or 0

    async def export_excel(self, db: AsyncSession, output_path: str) -> str:
        suppliers = (
            await db.execute(select(Supplier).order_by(Supplier.name))
        ).scalars().all()
        wb = Workbook()
        ws = wb.active
        ws.title = "Suppliers"
        headers = ["Code", "Name", "Email(s)", "Trades", "Contact", "Phone",
                   "Region", "Country", "Rating", "Active"]
        fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        font = Font(bold=True, color="FFFFFF")
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.fill = fill
            cell.font = font
        for r, s in enumerate(suppliers, 2):
            ws.cell(row=r, column=1, value=s.code)
            ws.cell(row=r, column=2, value=s.name)
            ws.cell(row=r, column=3, value=", ".join(s.emails or []))
            ws.cell(row=r, column=4, value=", ".join(s.trade_categories or []))
            ws.cell(row=r, column=5, value=s.contact_name)
            ws.cell(row=r, column=6, value=s.phone)
            ws.cell(row=r, column=7, value=s.region)
            ws.cell(row=r, column=8, value=s.country)
            ws.cell(row=r, column=9, value=s.rating)
            ws.cell(row=r, column=10, value="yes" if s.is_active else "no")
        for col_letter, width in zip("ABCDEFGHIJ", (12, 30, 35, 30, 20, 15, 15, 15, 10, 8)):
            ws.column_dimensions[col_letter].width = width
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return output_path
```

At the very bottom of the file (module level, after the class), add the helpers:

```python
def _norm_header(value) -> str:
    return str(value or "").lower().strip().replace(" ", "_")


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


def _split_multi(value: str | None, *, at_only: bool = False) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace(";", ",").split(",")]
    parts = [p for p in parts if p]
    if at_only:
        parts = [p for p in parts if "@" in p]
    return parts


def _norm_trade(value: str) -> str:
    return value.strip().lower().replace(" ", "_")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/suppliers/test_supplier_excel.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/supplier/supplier_service.py tests/suppliers/test_supplier_excel.py
git commit -m "feat(phase-9): supplier Excel import/export via openpyxl"
```

---

## Task 5: Suppliers API router

**Files:**
- Create: `app/api/suppliers.py`
- Modify: `app/main.py`
- Test: `tests/suppliers/test_suppliers_api.py`

Endpoints (global, single-user): `POST /api/suppliers`, `GET /api/suppliers` (filters), `GET /api/suppliers/{id}`, `PATCH /api/suppliers/{id}`, `POST /api/suppliers/{id}/blacklist`, `POST /api/suppliers/import` (xlsx upload), `GET /api/suppliers/export` (xlsx download).

- [ ] **Step 1: Write the failing tests**

Create `tests/suppliers/test_suppliers_api.py`:

```python
import io

import httpx
import openpyxl
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def api_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_crud_and_list(api_client):
    async with api_client as c:
        created = await c.post("/api/suppliers", json={
            "name": "Acme", "emails": ["a@x.test"], "trade_categories": ["mep"]})
        assert created.status_code == 201, created.text
        sid = created.json()["id"]
        assert created.json()["code"] == "SUP-0001"

        got = await c.get(f"/api/suppliers/{sid}")
        assert got.status_code == 200 and got.json()["name"] == "Acme"

        patched = await c.patch(f"/api/suppliers/{sid}", json={"rating": 4.2})
        assert patched.json()["rating"] == 4.2

        lst = await c.get("/api/suppliers", params={"trade": "mep"})
        assert lst.status_code == 200 and len(lst.json()) == 1
        assert (await c.get("/api/suppliers", params={"trade": "concrete"})).json() == []

        assert (await c.get("/api/suppliers/999999")).status_code == 404


async def test_blacklist(api_client):
    async with api_client as c:
        sid = (await c.post("/api/suppliers", json={"name": "B", "emails": [], "trade_categories": []})).json()["id"]
        r = await c.post(f"/api/suppliers/{sid}/blacklist", json={"reason": "fraud"})
        assert r.status_code == 200 and r.json()["is_blacklisted"] is True
        # blacklisted => inactive => not in default list
        assert (await c.get("/api/suppliers")).json() == []


async def test_import_and_export(api_client):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Name", "Email", "Trade"]); ws.append(["Acme", "a@x.test", "MEP"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    async with api_client as c:
        up = await c.post(
            "/api/suppliers/import",
            files={"file": ("sup.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert up.status_code == 200, up.text
        assert up.json()["imported"] == 1

        exp = await c.get("/api/suppliers/export")
        assert exp.status_code == 200
        assert exp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert len(exp.content) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/suppliers/test_suppliers_api.py -q`
Expected: FAIL — 404s / router not registered.

- [ ] **Step 3: Implement the router**

Create `app/api/suppliers.py`:

```python
"""Suppliers API: global supplier database (single-user) with Excel I/O."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.supplier import (
    BlacklistRequest,
    SupplierCreate,
    SupplierImportResult,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreate, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    data = payload.model_dump(exclude_unset=True)
    supplier = await SupplierService().create(
        db,
        name=data.pop("name"),
        emails=data.pop("emails", []),
        trade_categories=data.pop("trade_categories", []),
        **data,
    )
    return SupplierResponse.model_validate(supplier)


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    query: str | None = Query(default=None),
    trade: str | None = Query(default=None),
    region: str | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    min_rating: float | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[SupplierResponse]:
    suppliers = await SupplierService().list_suppliers(
        db, query=query, trade=trade, region=region,
        is_active=is_active, min_rating=min_rating,
    )
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.get("/export")
async def export_suppliers(db: AsyncSession = Depends(get_db)):
    out = Path(tempfile.gettempdir()) / "bidops_suppliers_export.xlsx"
    await SupplierService().export_excel(db, str(out))
    return FileResponse(
        str(out),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="suppliers.xlsx",
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    supplier = await SupplierService().get(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int, payload: SupplierUpdate, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    supplier = await SupplierService().update(
        db, supplier_id, **payload.model_dump(exclude_unset=True)
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.post("/{supplier_id}/blacklist", response_model=SupplierResponse)
async def blacklist_supplier(
    supplier_id: int, payload: BlacklistRequest, db: AsyncSession = Depends(get_db)
) -> SupplierResponse:
    supplier = await SupplierService().blacklist(db, supplier_id, payload.reason)
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return SupplierResponse.model_validate(supplier)


@router.post("/import", response_model=SupplierImportResult)
async def import_suppliers(
    file: UploadFile = File(...),
    update_existing: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> SupplierImportResult:
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = await SupplierService().import_excel(
            db, tmp_path, update_existing=update_existing
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return SupplierImportResult(**result)
```

> **Route-ordering note:** `/export` is declared **before** `/{supplier_id}` so FastAPI does not treat `export` as an `{supplier_id}` path value. Keep that order.

- [ ] **Step 4: Register the router in `app/main.py`**

Add the import alongside the other routers (after the `rules` import, ~line 20):

```python
from app.api.suppliers import router as suppliers_router
```

Add the registration alongside the other `app.include_router(...)` calls (after `packaging_router`, ~line 86):

```python
app.include_router(suppliers_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/suppliers/test_suppliers_api.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/suppliers.py app/main.py tests/suppliers/test_suppliers_api.py
git commit -m "feat(phase-9): suppliers API router (CRUD, search, import/export, blacklist)"
```

---

## Task 6: Email/RFQ schemas

**Files:**
- Create: `app/schemas/email.py`

- [ ] **Step 1: Write the schemas**

Create `app/schemas/email.py`:

```python
"""Schemas for RFQ creation, email drafts, and the email log."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RFQCreateRequest(BaseModel):
    supplier_ids: list[int]
    language: str | None = None  # "en" | "ar"; default per supplier/rules
    custom_message: str | None = None


class EmailUpdateRequest(BaseModel):
    """Edit a draft before sending. Only provided fields change."""

    subject: str | None = None
    body_html: str | None = None
    to: list[str] | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    reply_to: str | None = None


class EmailLogResponse(BaseModel):
    id: int
    package_id: int | None = None
    supplier_id: int | None = None
    offer_id: int | None = None
    email_type: str
    status: str
    to: list[str] = Field(default_factory=list)
    cc: list[str] | None = None
    bcc: list[str] | None = None
    subject: str
    body_html: str
    body_text: str | None = None
    attachments: list[dict] | None = None
    total_attachment_size: int | None = None
    from_address: str | None = None
    reply_to: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None

    model_config = {"from_attributes": True}


class RFQCreateResult(BaseModel):
    package_id: int
    drafts_created: int
    email_ids: list[int]
    skipped: list[str] = Field(default_factory=list)  # reasons, e.g. "no email on supplier 4"


class EmailSendResult(BaseModel):
    email_id: int
    status: str
    message_id: str | None = None
    error: str | None = None


class SuggestedSupplierResponse(BaseModel):
    id: int
    name: str
    emails: list[str] = Field(default_factory=list)
    trade_categories: list[str] = Field(default_factory=list)
    rating: float | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Verify import**

Run: `.venv/Scripts/python.exe -c "from app.schemas.email import RFQCreateRequest, EmailLogResponse; print(RFQCreateRequest(supplier_ids=[1,2]).language)"`
Expected: `None`

- [ ] **Step 3: Commit**

```bash
git add app/schemas/email.py
git commit -m "feat(phase-9): RFQ/email-log schemas"
```

---

## Task 7: Bilingual email templates

**Files:**
- Create: `app/services/email/__init__.py`, `app/services/email/templates.py`
- Test: `tests/email/__init__.py`, `tests/email/test_templates.py`

Jinja2 templates (autoescaped) for `rfq` and `reminder` in `en` and `ar`. Arabic templates set `dir="rtl"`. `render_body` falls back to `en` for an unknown language. `html_to_text` strips tags for the plain-text part.

- [ ] **Step 1: Write the failing tests**

Create `tests/email/__init__.py` (empty file).

Create `tests/email/test_templates.py`:

```python
import pytest

from app.services.email.templates import html_to_text, render_body

CTX = {
    "contact_name": "Sara",
    "project_name": "Metro",
    "package_name": "HVAC Package",
    "package_code": "PKG-001-HVAC",
    "trade_category": "Mep",
    "scope_description": "Supply & install <b>chillers</b>",
    "deadline": "2026-07-01",
    "submission_instructions": "Email your offer.",
    "attachments": [{"name": "Brief.pdf"}, {"name": "BOQ.xlsx"}],
    "sender_name": "BidOps AI",
    "company_name": "BidOps",
    "custom_message": "Note the site visit.",
}


def test_render_en_contains_key_fields_and_escapes():
    html = render_body("rfq", "en", CTX)
    assert "Sara" in html
    assert "HVAC Package" in html
    assert "Brief.pdf" in html and "BOQ.xlsx" in html
    assert "Note the site visit." in html
    # autoescape: the literal scope HTML must be escaped, not injected as a tag
    assert "<b>chillers</b>" not in html
    assert "&lt;b&gt;chillers&lt;/b&gt;" in html


def test_render_ar_is_rtl():
    html = render_body("rfq", "ar", CTX)
    assert 'dir="rtl"' in html
    assert "Sara" in html  # interpolated values still present


def test_unknown_language_falls_back_to_en():
    assert render_body("rfq", "fr", CTX) == render_body("rfq", "en", CTX)


def test_reminder_template_renders():
    html = render_body("reminder", "en", {**CTX, "time_remaining": "3 days"})
    assert "HVAC Package" in html


def test_html_to_text_strips_tags():
    txt = html_to_text("<p>Hello&nbsp;<b>World</b></p>")
    assert "Hello" in txt and "World" in txt
    assert "<" not in txt and ">" not in txt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_templates.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.email`.

- [ ] **Step 3: Implement the templates module**

Create `app/services/email/__init__.py` (empty file).

Create `app/services/email/templates.py`:

```python
"""Bilingual (en/ar) email body templates rendered with Jinja2.

Templates are HTML. Jinja2 autoescaping protects against injection from
user/supplier-controlled fields (scope text, custom messages). The plain-text
alternative is derived with html_to_text().
"""

from __future__ import annotations

import re

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

_RFQ_EN = """\
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {{ contact_name }},</p>
<p>We invite you to submit your quotation for the following package:</p>
<div style="background:#f5f5f5;padding:15px;margin:20px 0;border-radius:5px;">
  <p><strong>Project:</strong> {{ project_name }}</p>
  <p><strong>Package:</strong> {{ package_name }}</p>
  <p><strong>Package Code:</strong> {{ package_code }}</p>
  <p><strong>Trade:</strong> {{ trade_category }}</p>
</div>
<p><strong>Scope of Work:</strong></p>
<p>{{ scope_description }}</p>
<p><strong>Submission Deadline:</strong> {{ deadline }}</p>
<p><strong>Submission Instructions:</strong> {{ submission_instructions }}</p>
{% if custom_message %}<p><strong>Additional Notes:</strong> {{ custom_message }}</p>{% endif %}
<p>Documents attached:</p>
<ul>
{% for att in attachments %}<li>{{ att.name }}</li>
{% else %}<li>No attachments</li>
{% endfor %}</ul>
<p>We look forward to receiving your competitive offer.</p>
<p>Best regards,<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_RFQ_AR = """\
<html><body dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>السادة {{ contact_name }},</p>
<p>ندعوكم لتقديم عرض أسعاركم للحزمة التالية:</p>
<div style="background:#f5f5f5;padding:15px;margin:20px 0;border-radius:5px;">
  <p><strong>المشروع:</strong> {{ project_name }}</p>
  <p><strong>الحزمة:</strong> {{ package_name }}</p>
  <p><strong>رمز الحزمة:</strong> {{ package_code }}</p>
  <p><strong>التخصص:</strong> {{ trade_category }}</p>
</div>
<p><strong>نطاق العمل:</strong></p>
<p>{{ scope_description }}</p>
<p><strong>الموعد النهائي للتسليم:</strong> {{ deadline }}</p>
<p><strong>تعليمات التقديم:</strong> {{ submission_instructions }}</p>
{% if custom_message %}<p><strong>ملاحظات إضافية:</strong> {{ custom_message }}</p>{% endif %}
<p>المرفقات:</p>
<ul>
{% for att in attachments %}<li>{{ att.name }}</li>
{% else %}<li>لا توجد مرفقات</li>
{% endfor %}</ul>
<p>نتطلع إلى استلام عرضكم التنافسي.</p>
<p>مع خالص التحية،<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_REMINDER_EN = """\
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {{ contact_name }},</p>
<p>A friendly reminder that the submission deadline for the following package is approaching:</p>
<div style="background:#fff3cd;padding:15px;margin:20px 0;border-radius:5px;border-left:4px solid #ffc107;">
  <p><strong>Package:</strong> {{ package_name }}</p>
  <p><strong>Deadline:</strong> {{ deadline }}</p>
  <p><strong>Time Remaining:</strong> {{ time_remaining }}</p>
</div>
<p>If you have already submitted your quotation, please disregard this message.</p>
<p>Best regards,<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_REMINDER_AR = """\
<html><body dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>السادة {{ contact_name }},</p>
<p>تذكير ودي بأن الموعد النهائي لتسليم العروض للحزمة التالية يقترب:</p>
<div style="background:#fff3cd;padding:15px;margin:20px 0;border-radius:5px;border-left:4px solid #ffc107;">
  <p><strong>الحزمة:</strong> {{ package_name }}</p>
  <p><strong>الموعد النهائي:</strong> {{ deadline }}</p>
  <p><strong>الوقت المتبقي:</strong> {{ time_remaining }}</p>
</div>
<p>إذا كنتم قد قدمتم عرضكم بالفعل، يُرجى تجاهل هذه الرسالة.</p>
<p>مع خالص التحية،<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_TEMPLATES = {
    ("rfq", "en"): _RFQ_EN,
    ("rfq", "ar"): _RFQ_AR,
    ("reminder", "en"): _REMINDER_EN,
    ("reminder", "ar"): _REMINDER_AR,
}

SUPPORTED_TYPES = ("rfq", "reminder")
SUPPORTED_LANGS = ("en", "ar")


def render_body(email_type: str, language: str, context: dict) -> str:
    """Render an HTML email body. Falls back to English for unknown languages."""
    lang = language if language in SUPPORTED_LANGS else "en"
    source = _TEMPLATES.get((email_type, lang))
    if source is None:
        raise ValueError(f"No template for email_type={email_type!r}")
    # attachments is optional; default to empty list for the {% for %} loop.
    ctx = {"attachments": [], "custom_message": None, "time_remaining": "", **context}
    return _env.from_string(source).render(**ctx)


def html_to_text(html: str) -> str:
    """Crude HTML→text for the plain-text MIME alternative."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_templates.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/email/__init__.py app/services/email/templates.py tests/email/__init__.py tests/email/test_templates.py
git commit -m "feat(phase-9): bilingual (en/ar) RFQ + reminder email templates"
```

---

## Task 8: SMTPSender — injectable transport

**Files:**
- Create: `app/services/email/smtp_sender.py`
- Test: `tests/email/test_smtp_sender.py`

Pure transport. Reads settings; `is_configured()` is False when host/user are blank (then `/send` degrades to 503). `send(...)` builds a MIME message and returns a message-id; raises `SendError` on failure. Tests monkeypatch `smtplib.SMTP` so no real network is used.

- [ ] **Step 1: Write the failing tests**

Create `tests/email/test_smtp_sender.py`:

```python
import smtplib

import pytest

from app.services.email.smtp_sender import SendError, SMTPSender


def test_not_configured_when_blank():
    sender = SMTPSender(host="", user="")
    assert sender.is_configured() is False


def test_configured_when_host_and_user_present():
    sender = SMTPSender(host="smtp.test", port=587, user="me@test", password="pw")
    assert sender.is_configured() is True


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.sent = None
        self.tls = False
        self.logged_in = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent = (from_addr, list(to_addrs), msg)


def test_send_builds_message_and_returns_id(monkeypatch):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    sender = SMTPSender(host="smtp.test", port=587, user="me@test", password="pw", use_tls=True)
    msg_id = sender.send(
        from_address="me@test", from_name="BidOps", to=["a@x.test"], cc=["c@x.test"],
        bcc=["b@x.test"], reply_to="reply@test", subject="Hello", body_text="hi",
        body_html="<p>hi</p>", attachments=[],
    )
    assert msg_id  # non-empty Message-ID
    fake = _FakeSMTP.instances[-1]
    assert fake.tls is True
    assert fake.logged_in == ("me@test", "pw")
    from_addr, recipients, raw = fake.sent
    assert from_addr == "me@test"
    # all of to/cc/bcc are in the envelope recipients
    assert set(recipients) == {"a@x.test", "c@x.test", "b@x.test"}
    assert "Subject: Hello" in raw


def test_send_attaches_files(monkeypatch, tmp_path):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    f = tmp_path / "doc.txt"
    f.write_text("payload")
    sender = SMTPSender(host="smtp.test", user="me@test", password="pw")
    sender.send(
        from_address="me@test", from_name="B", to=["a@x.test"], cc=None, bcc=None,
        reply_to=None, subject="S", body_text="t", body_html="<p>t</p>",
        attachments=[{"name": "doc.txt", "path": str(f)}],
    )
    raw = _FakeSMTP.instances[-1].sent[2]
    assert "doc.txt" in raw


def test_send_wraps_failure_in_senderror(monkeypatch):
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", _boom)
    sender = SMTPSender(host="smtp.test", user="me@test", password="pw")
    with pytest.raises(SendError):
        sender.send(
            from_address="me@test", from_name="B", to=["a@x.test"], cc=None, bcc=None,
            reply_to=None, subject="S", body_text="t", body_html="<p>t</p>", attachments=[],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_smtp_sender.py -q`
Expected: FAIL — `ModuleNotFoundError: ...smtp_sender`.

- [ ] **Step 3: Implement the sender**

Create `app/services/email/smtp_sender.py`:

```python
"""SMTP transport for outbound email. Injectable boundary for testability.

This module knows nothing about EmailLog/DB — it just sends a message. The
default constructor reads credentials from settings; pass explicit kwargs (or a
fake) in tests. is_configured() gates POST /send so missing creds degrade to a
clean 503 instead of a crash.
"""

from __future__ import annotations

import smtplib
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from pathlib import Path

from app.config import get_settings


class SendError(Exception):
    """Raised when the SMTP transport fails to send a message."""


class SMTPSender:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool | None = None,
        timeout: int = 30,
    ) -> None:
        s = get_settings()
        self.host = host if host is not None else s.smtp_host
        self.port = port if port is not None else s.smtp_port
        self.user = user if user is not None else s.smtp_user
        self.password = password if password is not None else s.smtp_password
        self.use_tls = use_tls if use_tls is not None else s.smtp_use_tls
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.host and self.user)

    def send(
        self,
        *,
        from_address: str,
        from_name: str,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        reply_to: str | None,
        subject: str,
        body_text: str | None,
        body_html: str,
        attachments: list[dict] | None,
    ) -> str:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_address}>" if from_name else from_address
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to
        message_id = make_msgid()
        msg["Message-ID"] = message_id

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text or "", "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)

        for att in attachments or []:
            path = Path(att["path"])
            if not path.exists():
                continue
            part = MIMEApplication(path.read_bytes(), Name=att["name"])
            part["Content-Disposition"] = f'attachment; filename="{att["name"]}"'
            msg.attach(part)

        recipients = list(to) + list(cc or []) + list(bcc or [])
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls()
                if self.user:
                    server.login(self.user, self.password)
                server.sendmail(from_address, recipients, msg.as_string())
        except Exception as exc:  # noqa: BLE001 - normalize to SendError for callers
            raise SendError(str(exc)) from exc
        return message_id
```

> Note: `uuid` is imported defensively in case a future caller needs a fallback id; `make_msgid()` is the primary source. If a linter flags the unused import, remove the `import uuid` line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_smtp_sender.py -q`
Expected: PASS (5 tests).

> If `import uuid` triggers an unused-import failure in CI/linters, delete that line and re-run. (There is no linter gate in this repo's test command, so it is safe either way; prefer removing it to keep things clean.)

- [ ] **Step 5: Commit**

```bash
git add app/services/email/smtp_sender.py tests/email/test_smtp_sender.py
git commit -m "feat(phase-9): injectable SMTPSender transport with graceful config gate"
```

---

## Task 9: RFQService — drafts, attachments, suggested suppliers, send

**Files:**
- Create: `app/services/email/rfq_service.py`
- Test: `tests/email/test_rfq_service.py`

The heart of the phase. `create_rfq_drafts` only ever produces `DRAFT` `EmailLog` rows (never sends). `send` is a separate explicit call that uses an injected/`default` `SMTPSender`, flips status to `SENT` (or `FAILED`), and bumps the supplier's `total_rfqs_sent`. Language is per-supplier (`preferred_language`) unless overridden, falling back to `rules.email.default_language`. From-address resolves `rules.email.from_address → settings.email_from → settings.smtp_user`. Attachments are collected from the package's exported folder (brief + `Documents/`) honoring `rules.email.attachment_size_limit_mb`.

- [ ] **Step 1: Write the failing tests**

Create `tests/email/test_rfq_service.py`:

```python
import pytest

from app.models.base import EmailStatus, EmailType
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier
from app.services.email.rfq_service import RFQService
from app.services.email.smtp_sender import SendError


async def _seed(db):
    project = Project(name="Metro Line 3")
    db.add(project)
    await db.flush()
    package = Package(
        project_id=project.id, name="HVAC Works", code="PKG-001-MEP",
        trade_category="mep", description="Supply and install HVAC.",
    )
    db.add(package)
    sup_en = Supplier(name="CoolAir", emails=["sales@coolair.test"],
                      trade_categories=["mep"], preferred_language="en", contact_name="Sam")
    sup_ar = Supplier(name="HawaCo", emails=["bids@hawa.test"],
                      trade_categories=["mep"], preferred_language="ar")
    sup_none = Supplier(name="NoEmail", emails=[], trade_categories=["mep"])
    db.add_all([sup_en, sup_ar, sup_none])
    await db.commit()
    for obj in (package, sup_en, sup_ar, sup_none):
        await db.refresh(obj)
    return project, package, sup_en, sup_ar, sup_none


async def test_suggested_suppliers_matches_trade(db_session):
    _, package, sup_en, sup_ar, sup_none = await _seed(db_session)
    suggestions = await RFQService().suggested_suppliers(db_session, package.id)
    names = {s.name for s in suggestions}
    assert {"CoolAir", "HawaCo", "NoEmail"} <= names


async def test_create_rfq_drafts_are_drafts_only(db_session):
    _, package, sup_en, sup_ar, sup_none = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(
        db_session, package.id, [sup_en.id, sup_ar.id]
    )
    assert len(drafts) == 2
    for d in drafts:
        assert d.status == EmailStatus.DRAFT.value
        assert d.email_type == EmailType.RFQ.value
        assert d.sent_at is None
    # language honored: Arabic supplier draft is RTL
    ar_draft = next(d for d in drafts if d.supplier_id == sup_ar.id)
    assert 'dir="rtl"' in ar_draft.body_html
    en_draft = next(d for d in drafts if d.supplier_id == sup_en.id)
    assert "CoolAir" not in en_draft.body_html  # uses contact_name, not company
    assert "Sam" in en_draft.body_html
    assert en_draft.to == ["sales@coolair.test"]


async def test_create_rfq_skips_supplier_without_email(db_session):
    _, package, sup_en, sup_ar, sup_none = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(db_session, package.id, [sup_none.id])
    assert drafts == []


async def test_language_override(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(
        db_session, package.id, [sup_en.id], language="ar"
    )
    assert 'dir="rtl"' in drafts[0].body_html


async def test_subject_uses_rules_format(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(db_session, package.id, [sup_en.id])
    # default rules.email.subject_formats.rfq = "[{project_code}] RFQ - {package_name}"
    assert drafts[0].subject == "[Metro Line 3] RFQ - HVAC Works"


async def test_list_get_and_update_draft(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    assert (await svc.get_email(db_session, draft.id)).id == draft.id
    listed = await svc.list_emails(db_session, package_id=package.id)
    assert len(listed) == 1
    updated = await svc.update_draft(db_session, draft.id, subject="Edited", to=["new@x.test"])
    assert updated.subject == "Edited"
    assert updated.to == ["new@x.test"]


async def test_update_draft_rejects_sent(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    draft.status = EmailStatus.SENT.value
    await db_session.commit()
    with pytest.raises(ValueError):
        await svc.update_draft(db_session, draft.id, subject="too late")


class _FakeSender:
    def __init__(self, configured=True, fail=False):
        self._configured = configured
        self._fail = fail
        self.calls = []

    def is_configured(self):
        return self._configured

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail:
            raise SendError("smtp boom")
        return "<msgid@test>"


async def test_send_uses_injected_sender_and_marks_sent(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    sender = _FakeSender()
    out = await svc.send(db_session, draft.id, sender=sender)
    assert out.status == EmailStatus.SENT.value
    assert out.message_id == "<msgid@test>"
    assert out.sent_at is not None
    assert len(sender.calls) == 1
    # supplier RFQ counter incremented
    refreshed = await db_session.get(Supplier, sup_en.id)
    assert refreshed.total_rfqs_sent == 1


async def test_send_failure_marks_failed(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    out = await svc.send(db_session, draft.id, sender=_FakeSender(fail=True))
    assert out.status == EmailStatus.FAILED.value
    assert out.error_message and "boom" in out.error_message


async def test_send_raises_when_not_configured(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    with pytest.raises(RuntimeError):
        await svc.send(db_session, draft.id, sender=_FakeSender(configured=False))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_rfq_service.py -q`
Expected: FAIL — `ModuleNotFoundError: ...rfq_service`.

- [ ] **Step 3: Implement the service**

Create `app/services/email/rfq_service.py`:

```python
"""RFQ email orchestration: build draft EmailLogs per package×supplier, list/
edit drafts, and send (explicit, separate step) via an injectable SMTPSender.

Draft-only by design: create_rfq_drafts NEVER sends. Nothing is auto-sent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EmailStatus, EmailType
from app.models.email import EmailLog
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier
from app.services.email.smtp_sender import SendError, SMTPSender
from app.services.email.templates import html_to_text, render_body
from app.services.rules.rules_service import RulesService

logger = logging.getLogger(__name__)

# Draft fields that may be edited before sending.
_EDITABLE = ("subject", "body_html", "to", "cc", "bcc", "reply_to")


class RFQService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    def _rules(self):
        return self._rules_service.load()

    async def suggested_suppliers(
        self, db: AsyncSession, package_id: int
    ) -> list[Supplier]:
        package = await db.get(Package, package_id)
        if package is None:
            return []
        from app.services.supplier.supplier_service import SupplierService

        return await SupplierService().suppliers_for_trade(db, package.trade_category)

    def _from_address(self, rules) -> str:
        from app.config import get_settings

        s = get_settings()
        return rules.email.from_address or s.email_from or s.smtp_user or ""

    def _collect_attachments(
        self, package: Package, limit_mb: int
    ) -> tuple[list[dict], int, list[str]]:
        limit_bytes = max(limit_mb, 0) * 1024 * 1024
        candidates: list[Path] = []
        if package.brief_path:
            candidates.append(Path(package.brief_path))
        if package.folder_path:
            docs_dir = Path(package.folder_path) / "Documents"
            if docs_dir.is_dir():
                candidates += sorted(p for p in docs_dir.iterdir() if p.is_file())
        items: list[dict] = []
        total = 0
        skipped: list[str] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key in seen or not path.exists():
                continue
            seen.add(key)
            size = path.stat().st_size
            if limit_bytes and total + size > limit_bytes:
                skipped.append(path.name)
                continue
            items.append({"name": path.name, "path": key, "size": size})
            total += size
        return items, total, skipped

    async def create_rfq_drafts(
        self,
        db: AsyncSession,
        package_id: int,
        supplier_ids: list[int],
        *,
        language: str | None = None,
        custom_message: str | None = None,
    ) -> list[EmailLog]:
        package = await db.get(Package, package_id)
        if package is None:
            raise ValueError(f"Package {package_id} not found")
        project = await db.get(Project, package.project_id)
        rules = self._rules()
        from_address = self._from_address(rules)
        reply_to = rules.email.reply_to or None
        attachments, total_size, _skipped = self._collect_attachments(
            package, rules.email.attachment_size_limit_mb
        )
        project_name = project.name if project else "Project"
        subject_fmt = rules.email.subject_formats.rfq

        drafts: list[EmailLog] = []
        for supplier_id in supplier_ids:
            supplier = await db.get(Supplier, supplier_id)
            if supplier is None or not supplier.emails:
                logger.info("Skipping supplier %s: missing or no email", supplier_id)
                continue
            lang = (
                language
                or supplier.preferred_language
                or rules.email.default_language
                or "en"
            )
            context = {
                "contact_name": supplier.contact_name or supplier.name,
                "project_name": project_name,
                "package_name": package.name,
                "package_code": package.code,
                "trade_category": (package.trade_category or "").replace("_", " ").title(),
                "scope_description": package.description or "Please refer to attached documents.",
                "deadline": (
                    package.submission_deadline.strftime("%Y-%m-%d")
                    if package.submission_deadline
                    else "To be confirmed"
                ),
                "submission_instructions": (
                    package.submission_instructions or "Please submit your quotation via email."
                ),
                "attachments": attachments,
                "custom_message": custom_message,
                "sender_name": get_settings_name(),
                "company_name": company_name(),
            }
            body_html = render_body("rfq", lang, context)
            subject = _safe_format(
                subject_fmt,
                project_code=project_name,
                package_name=package.name,
                package_code=package.code,
                supplier_name=supplier.name,
            )
            email_log = EmailLog(
                package_id=package.id,
                supplier_id=supplier.id,
                email_type=EmailType.RFQ.value,
                status=EmailStatus.DRAFT.value,
                to=list(supplier.emails),
                subject=subject,
                body_html=body_html,
                body_text=html_to_text(body_html),
                attachments=attachments or None,
                total_attachment_size=total_size or None,
                from_address=from_address or None,
                reply_to=reply_to,
            )
            db.add(email_log)
            drafts.append(email_log)

        await db.commit()
        for d in drafts:
            await db.refresh(d)
        return drafts

    async def get_email(self, db: AsyncSession, email_id: int) -> EmailLog | None:
        return await db.get(EmailLog, email_id)

    async def list_emails(
        self,
        db: AsyncSession,
        *,
        package_id: int | None = None,
        supplier_id: int | None = None,
        email_type: str | None = None,
        status: str | None = None,
    ) -> list[EmailLog]:
        stmt = select(EmailLog)
        if package_id is not None:
            stmt = stmt.where(EmailLog.package_id == package_id)
        if supplier_id is not None:
            stmt = stmt.where(EmailLog.supplier_id == supplier_id)
        if email_type is not None:
            stmt = stmt.where(EmailLog.email_type == email_type)
        if status is not None:
            stmt = stmt.where(EmailLog.status == status)
        stmt = stmt.order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
        return list((await db.execute(stmt)).scalars().all())

    async def update_draft(
        self, db: AsyncSession, email_id: int, **fields
    ) -> EmailLog | None:
        email_log = await db.get(EmailLog, email_id)
        if email_log is None:
            return None
        if email_log.status != EmailStatus.DRAFT.value:
            raise ValueError("Only DRAFT emails can be edited")
        for key, value in fields.items():
            if value is None or key not in _EDITABLE:
                continue
            setattr(email_log, key, value)
        if "body_html" in fields and fields["body_html"]:
            email_log.body_text = html_to_text(fields["body_html"])
        await db.commit()
        await db.refresh(email_log)
        return email_log

    async def send(
        self,
        db: AsyncSession,
        email_id: int,
        *,
        sender: SMTPSender | None = None,
    ) -> EmailLog:
        email_log = await db.get(EmailLog, email_id)
        if email_log is None:
            raise ValueError(f"Email {email_id} not found")
        if email_log.status == EmailStatus.SENT.value:
            return email_log
        sender = sender or SMTPSender()
        if not sender.is_configured():
            raise RuntimeError(
                "SMTP is not configured. Set BIDOPS_SMTP_HOST/USER/PASSWORD in .env."
            )
        try:
            message_id = sender.send(
                from_address=email_log.from_address or "",
                from_name=from_name(),
                to=list(email_log.to or []),
                cc=email_log.cc,
                bcc=email_log.bcc,
                reply_to=email_log.reply_to,
                subject=email_log.subject,
                body_text=email_log.body_text,
                body_html=email_log.body_html,
                attachments=email_log.attachments,
            )
        except SendError as exc:
            email_log.status = EmailStatus.FAILED.value
            email_log.error_message = str(exc)
            email_log.retry_count += 1
            await db.commit()
            await db.refresh(email_log)
            return email_log

        email_log.status = EmailStatus.SENT.value
        email_log.sent_at = datetime.now(timezone.utc)
        email_log.message_id = message_id
        if email_log.supplier_id and email_log.email_type == EmailType.RFQ.value:
            supplier = await db.get(Supplier, email_log.supplier_id)
            if supplier is not None:
                supplier.total_rfqs_sent = (supplier.total_rfqs_sent or 0) + 1
        await db.commit()
        await db.refresh(email_log)
        return email_log


def _safe_format(template: str, **values) -> str:
    """str.format that never raises on a missing/extra placeholder."""

    class _Default(dict):
        def __missing__(self, key):  # noqa: D401
            return "{" + key + "}"

    return template.format_map(_Default(values))


def get_settings_name() -> str:
    from app.config import get_settings

    return get_settings().email_from_name


def from_name() -> str:
    return get_settings_name()


def company_name() -> str:
    from app.config import get_settings

    return get_settings().company_name
```

> Implementation notes for the engineer:
> - `_from_address` and the small `get_settings_name`/`from_name`/`company_name` helpers read settings lazily so tests that tweak env still work. Keeping them as module functions (not constants) avoids capturing settings at import time.
> - `EmailLog(to=...)` uses the **Python attr** `to` (column `to_addresses`). Do not write `to_addresses=`.
> - Enum columns get `.value`. Comparisons use `.value`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_rfq_service.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/email/rfq_service.py tests/email/test_rfq_service.py
git commit -m "feat(phase-9): RFQService — draft-only RFQ creation, edit, and explicit send"
```

---

## Task 10: Emails API router

**Files:**
- Create: `app/api/emails.py`
- Modify: `app/main.py`
- Test: `tests/email/test_emails_api.py`

Endpoints:
- `GET  /api/projects/{project_id}/packages/{package_id}/suggested-suppliers` → suppliers matching the package trade.
- `POST /api/projects/{project_id}/packages/{package_id}/rfq` → create draft RFQs for supplier_ids (returns `RFQCreateResult`).
- `GET  /api/emails` → email log (filters: package_id, supplier_id, email_type, status).
- `GET  /api/emails/{email_id}` → one email (preview).
- `PATCH /api/emails/{email_id}` → edit a draft.
- `POST /api/emails/{email_id}/send` → explicit send (503 if SMTP not configured).

- [ ] **Step 1: Write the failing tests**

Create `tests/email/test_emails_api.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def emails_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.package import Package
    from app.models.project import Project
    from app.models.supplier import Supplier

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                          trade_category="mep", description="HVAC scope")
        seed.add(package)
        seed.add(Supplier(name="CoolAir", emails=["s@coolair.test"],
                          trade_categories=["mep"], preferred_language="en"))
        await seed.commit()
        ids = {"project": project.id, "package": package.id}
        sup = (await seed.execute(
            __import__("sqlalchemy").select(Supplier))).scalars().first()
        ids["supplier"] = sup.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, ids
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_suggested_then_create_and_preview(emails_client):
    client, ids = emails_client
    async with client as c:
        sug = await c.get(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/suggested-suppliers")
        assert sug.status_code == 200
        assert any(s["id"] == ids["supplier"] for s in sug.json())

        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        assert rfq.status_code == 201, rfq.text
        body = rfq.json()
        assert body["drafts_created"] == 1
        email_id = body["email_ids"][0]

        preview = await c.get(f"/api/emails/{email_id}")
        assert preview.status_code == 200
        assert preview.json()["status"] == "draft"
        assert preview.json()["subject"] == "[Metro] RFQ - HVAC"

        log = await c.get("/api/emails", params={"package_id": ids["package"]})
        assert log.status_code == 200 and len(log.json()) == 1


async def test_edit_draft(emails_client):
    client, ids = emails_client
    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        patched = await c.patch(f"/api/emails/{email_id}", json={"subject": "Custom RFQ"})
        assert patched.status_code == 200
        assert patched.json()["subject"] == "Custom RFQ"


async def test_send_returns_503_when_smtp_not_configured(emails_client):
    client, ids = emails_client
    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        # Test settings have no SMTP host/user => SMTPSender.is_configured() False
        send = await c.post(f"/api/emails/{email_id}/send")
        assert send.status_code == 503, send.text


async def test_send_succeeds_with_injected_sender(emails_client, monkeypatch):
    import app.api.emails as emails_api

    client, ids = emails_client

    class _FakeSender:
        def is_configured(self):
            return True

        def send(self, **kwargs):
            return "<msgid@test>"

    monkeypatch.setattr(emails_api, "SMTPSender", lambda: _FakeSender())

    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        send = await c.post(f"/api/emails/{email_id}/send")
        assert send.status_code == 200, send.text
        assert send.json()["status"] == "sent"
        assert send.json()["message_id"] == "<msgid@test>"


async def test_rfq_404_missing_package(emails_client):
    client, ids = emails_client
    async with client as c:
        r = await c.post(
            f"/api/projects/{ids['project']}/packages/999999/rfq",
            json={"supplier_ids": [ids["supplier"]]})
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_emails_api.py -q`
Expected: FAIL — router not registered / 404s.

- [ ] **Step 3: Implement the router**

Create `app/api/emails.py`:

```python
"""Emails API: suggested suppliers, draft-only RFQ creation, email log, and
explicit send. Nothing is auto-sent — send is always a separate POST.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.package import Package
from app.schemas.email import (
    EmailLogResponse,
    EmailSendResult,
    EmailUpdateRequest,
    RFQCreateRequest,
    RFQCreateResult,
    SuggestedSupplierResponse,
)
from app.services.email.rfq_service import RFQService
from app.services.email.smtp_sender import SMTPSender

router = APIRouter(tags=["emails"])


async def _require_package(db: AsyncSession, project_id: int, package_id: int) -> Package:
    package = await db.get(Package, package_id)
    if package is None or package.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    return package


@router.get(
    "/projects/{project_id}/packages/{package_id}/suggested-suppliers",
    response_model=list[SuggestedSupplierResponse],
)
async def suggested_suppliers(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> list[SuggestedSupplierResponse]:
    await _require_package(db, project_id, package_id)
    suppliers = await RFQService().suggested_suppliers(db, package_id)
    return [SuggestedSupplierResponse.model_validate(s) for s in suppliers]


@router.post(
    "/projects/{project_id}/packages/{package_id}/rfq",
    response_model=RFQCreateResult,
    status_code=201,
)
async def create_rfq(
    project_id: int,
    package_id: int,
    payload: RFQCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> RFQCreateResult:
    await _require_package(db, project_id, package_id)
    requested = set(payload.supplier_ids)
    drafts = await RFQService().create_rfq_drafts(
        db, package_id, payload.supplier_ids,
        language=payload.language, custom_message=payload.custom_message,
    )
    created_supplier_ids = {d.supplier_id for d in drafts}
    skipped = [
        f"supplier {sid}: missing or no email address"
        for sid in requested
        if sid not in created_supplier_ids
    ]
    return RFQCreateResult(
        package_id=package_id,
        drafts_created=len(drafts),
        email_ids=[d.id for d in drafts],
        skipped=skipped,
    )


@router.get("/emails", response_model=list[EmailLogResponse])
async def list_emails(
    package_id: int | None = Query(default=None),
    supplier_id: int | None = Query(default=None),
    email_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[EmailLogResponse]:
    emails = await RFQService().list_emails(
        db, package_id=package_id, supplier_id=supplier_id,
        email_type=email_type, status=status,
    )
    return [EmailLogResponse.model_validate(e) for e in emails]


@router.get("/emails/{email_id}", response_model=EmailLogResponse)
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)) -> EmailLogResponse:
    email_log = await RFQService().get_email(db, email_id)
    if email_log is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    return EmailLogResponse.model_validate(email_log)


@router.patch("/emails/{email_id}", response_model=EmailLogResponse)
async def update_email(
    email_id: int, payload: EmailUpdateRequest, db: AsyncSession = Depends(get_db)
) -> EmailLogResponse:
    try:
        email_log = await RFQService().update_draft(
            db, email_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if email_log is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    return EmailLogResponse.model_validate(email_log)


@router.post("/emails/{email_id}/send", response_model=EmailSendResult)
async def send_email(email_id: int, db: AsyncSession = Depends(get_db)) -> EmailSendResult:
    svc = RFQService()
    if await svc.get_email(db, email_id) is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    try:
        email_log = await svc.send(db, email_id, sender=SMTPSender())
    except RuntimeError as exc:  # SMTP not configured
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EmailSendResult(
        email_id=email_log.id,
        status=email_log.status,
        message_id=email_log.message_id,
        error=email_log.error_message,
    )
```

> **Why `SMTPSender` is referenced at module level in the router:** the test monkeypatches `app.api.emails.SMTPSender` to inject a fake. Keep `from app.services.email.smtp_sender import SMTPSender` at the top and call `SMTPSender()` inside the handler (do not import it locally inside the function).

- [ ] **Step 4: Register the router in `app/main.py`**

Add the import (after `suppliers_router`):

```python
from app.api.emails import router as emails_router
```

Add the registration (after `suppliers_router`):

```python
app.include_router(emails_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_emails_api.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/emails.py app/main.py tests/email/test_emails_api.py
git commit -m "feat(phase-9): emails API — suggested suppliers, RFQ drafts, log, explicit send"
```

---

## Task 11: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS. Baseline was 58; this phase adds 8 + 5 + 3 + 5 + 5 + 11 + 5 = **42** new tests → **100 passing** (exact count may vary by ±a couple if the engineer split/merged a case; the requirement is **zero failures and no skips beyond the known easyocr/weasyprint env skips**, which are not touched here).

- [ ] **Step 2: Smoke-check the app imports and routes register**

Run:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'supplier' in p or 'email' in p or 'rfq' in p))"
```
Expected (order may differ):
```
/api/emails
/api/emails/{email_id}
/api/emails/{email_id}/send
/api/projects/{project_id}/packages/{package_id}/rfq
/api/projects/{project_id}/packages/{package_id}/suggested-suppliers
/api/suppliers
/api/suppliers/export
/api/suppliers/import
/api/suppliers/{supplier_id}
/api/suppliers/{supplier_id}/blacklist
```

- [ ] **Step 3: Final commit (if anything is uncommitted)**

```bash
git add -A
git commit -m "test(phase-9): full suite green — suppliers + draft-only RFQ email"
```

---

## Spec Coverage Self-Review

| Phase 9 spec requirement (spec §6 / roadmap) | Task |
|---|---|
| Supplier DB (CRUD) | 2, 3, 5 |
| Supplier Excel import/export | 4, 5 |
| Supplier search / trade matching | 3, 5, 10 (suggested-suppliers) |
| SMTP draft-only RFQ | 7, 8, 9, 10 |
| Bilingual (en/ar) RFQ | 7, 9 |
| Mandatory preview (never auto-send) | 9 (drafts only), 10 (separate `/send`) |
| Email log | 6, 9 (`list_emails`), 10 (`GET /emails`) |
| Configurable market (from-address, subjects, language, size cap from rules) | 9 |
| Graceful degradation when SMTP absent | 8 (`is_configured`), 10 (503) |
| No hardcoded currency/VAT/locale introduced | n/a (this phase adds none) |

**Deferred to later phases (intentionally NOT in Phase 9):** clarification emails + comparison/scoring (Phase 10), award/regret letters (Phase 14), supplier-offer ingestion (Phase 10), React UI for these screens (Phase 6C). The `reminder` template is included opportunistically because it is part of the RFQ lifecycle and trivially shares the rendering path; no reminder *scheduling* is built (out of scope).

**SMTP enablement note (for the human, not the implementer):** real sending requires `BIDOPS_SMTP_HOST`, `BIDOPS_SMTP_USER`, `BIDOPS_SMTP_PASSWORD` (and optionally `BIDOPS_SMTP_PORT`, `BIDOPS_SMTP_USE_TLS`, `BIDOPS_EMAIL_FROM`, `BIDOPS_EMAIL_FROM_NAME`, `BIDOPS_COMPANY_NAME`) in the root `.env`. The SMTP creds currently live only in `bidops-ai/.env` (unprefixed `SMTP_*`); they must be copied with the `BIDOPS_` prefix. Until then, all draft/preview/log functionality works and `/send` returns a clean 503 — which is consistent with the locked "mandatory draft-only" decision.
```
