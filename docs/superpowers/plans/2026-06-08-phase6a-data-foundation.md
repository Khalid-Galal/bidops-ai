# Phase 6A — Data-Model Foundation + Test Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a pytest async test harness and port the 7 v2-domain SQLAlchemy models (BOQ, Package, Supplier/Offer, Email, Audit, User/Organization) from the `bidops-ai/` scaffold onto the root app's async `Base`, with verified table creation and CRUD round-trips.

**Architecture:** The root app (`app/`) uses async SQLAlchemy 2.0 (`Mapped[]` + `mapped_column`), tables auto-created at startup via `Base.metadata.create_all`. We make `app/models/base.py` API-compatible with the scaffold's base (add `TimestampMixin` + v2 enums) so the scaffold's model files port over with minimal edits. Each ported model is registered in `app/models/__init__.py` so `create_all` picks it up, and verified by an async round-trip test against a temporary SQLite DB.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 async, aiosqlite, pytest, pytest-asyncio, alembic.

**Source of truth for schemas:** `bidops-ai/backend/app/models/{boq,package,supplier,email,audit,user}.py` (read each during its task). These already use the same `Mapped[]`/`app.models.base` idiom, so porting is mostly import-compatibility + replacing any Postgres-only column types (`JSONB`→`JSON`, `ARRAY(...)`→`JSON`) with SQLite-friendly ones.

**Decomposition note:** This is plan **6A** of Phase 6. Sibling plans (separate): **6B** configurable rules/market system, **6C** React SPA shell on the v1 JSON API. 6B and 6C depend on 6A.

---

## File Structure

- `app/models/base.py` — MODIFY: add `TimestampMixin` + v2 enums (`DocumentCategory`, `PackageStatus`, `OfferStatus`, `EmailType`, `EmailStatus`, `UserRole`). Leave existing `Base`, `ProjectStatus`, `DocumentStatus` untouched.
- `app/models/boq.py` — CREATE: `BOQItem`.
- `app/models/package.py` — CREATE: `Package`, `PackageDocument`.
- `app/models/supplier.py` — CREATE: `Supplier`, `SupplierOffer`.
- `app/models/email.py` — CREATE: `EmailLog`.
- `app/models/audit.py` — CREATE: `AuditLog`.
- `app/models/user.py` — CREATE: `Organization`, `User`.
- `app/models/__init__.py` — MODIFY: import + export all new models (registers them with `Base.metadata`).
- `pyproject.toml` — MODIFY: add `[tool.pytest.ini_options]`.
- `tests/__init__.py`, `tests/conftest.py` — CREATE: async temp-DB fixtures.
- `tests/models/test_*.py` — CREATE: one round-trip test module per model group.
- `migrations/versions/*_v2_domain_models.py` — CREATE (Task 10): alembic migration.

---

## Task 1: pytest async harness

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_harness.py`

- [ ] **Step 1: Add pytest deps to the venv**

Run: `.venv/Scripts/python.exe -m pip install pytest pytest-asyncio`
Expected: installs successfully.

- [ ] **Step 2: Add pytest config to `pyproject.toml`**

Append:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `tests/conftest.py` with an isolated async DB session fixture**

```python
"""Pytest fixtures: isolated in-memory async SQLAlchemy session per test."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base  # noqa: F401 -- ensures all models are registered


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fresh in-memory SQLite database with all tables, per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
```

- [ ] **Step 5: Create `tests/test_harness.py` (sanity test)**

```python
async def test_harness_creates_tables(db_session):
    from sqlalchemy import text
    rows = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    names = {r[0] for r in rows}
    assert "projects" in names  # existing model proves create_all + registration work
```

- [ ] **Step 6: Run the harness test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_harness.py -v`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/conftest.py tests/test_harness.py
git commit -m "test: add pytest async harness with isolated in-memory DB fixture"
```

---

## Task 2: v2 enums + TimestampMixin in `app/models/base.py`

**Files:**
- Modify: `app/models/base.py`
- Test: `tests/models/test_enums.py`

- [ ] **Step 1: Create `tests/models/__init__.py`** (empty) and **write the failing test** `tests/models/test_enums.py`

```python
def test_v2_enums_present():
    from app.models.base import (
        TimestampMixin, DocumentCategory, PackageStatus,
        OfferStatus, EmailType, EmailStatus, UserRole,
    )
    assert PackageStatus.DRAFT.value == "draft"
    assert OfferStatus.SELECTED.value == "selected"
    assert UserRole.ESTIMATOR.value == "estimator"
    assert EmailType.RFQ.value == "rfq"
    assert EmailStatus.SENT.value == "sent"
    assert DocumentCategory.BOQ.value == "boq"
    assert hasattr(TimestampMixin, "created_at")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_enums.py -v`
Expected: FAIL (ImportError: cannot import name 'TimestampMixin').

- [ ] **Step 3: Append enums + mixin to `app/models/base.py`**

Add these imports at the top (keep existing `import enum`):

```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
```

Append at the end of the file (do NOT modify existing `Base`, `ProjectStatus`, `DocumentStatus`):

```python
class DocumentCategory(str, enum.Enum):
    ITT = "itt"
    SPECS = "specs"
    BOQ = "boq"
    DRAWINGS = "drawings"
    CONTRACT = "contract"
    ADDENDUM = "addendum"
    CORRESPONDENCE = "correspondence"
    SCHEDULE = "schedule"
    HSE = "hse"
    GENERAL = "general"
    UNKNOWN = "unknown"


class PackageStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    OFFERS_RECEIVED = "offers_received"
    EVALUATED = "evaluated"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class OfferStatus(str, enum.Enum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    CLARIFICATION_SENT = "clarification_sent"
    CLARIFICATION_RECEIVED = "clarification_received"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    SELECTED = "selected"
    REJECTED = "rejected"


class EmailType(str, enum.Enum):
    RFQ = "rfq"
    CLARIFICATION = "clarification"
    REMINDER = "reminder"
    AWARD = "award"
    REJECTION = "rejection"
    GENERAL = "general"


class EmailStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TENDER_MANAGER = "tender_manager"
    ESTIMATOR = "estimator"
    VIEWER = "viewer"


class TimestampMixin:
    """Mixin providing created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_enums.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/base.py tests/models/__init__.py tests/models/test_enums.py
git commit -m "feat(models): add v2 enums and TimestampMixin to base (API-compatible with scaffold)"
```

---

## Task 3: Port `BOQItem` model

**Files:**
- Create: `app/models/boq.py` (port from `bidops-ai/backend/app/models/boq.py`)
- Modify: `app/models/__init__.py`
- Test: `tests/models/test_boq.py`

- [ ] **Step 1: Write the failing test `tests/models/test_boq.py`**

```python
async def test_boq_item_roundtrip(db_session):
    from app.models.boq import BOQItem
    from app.models.project import Project

    project = Project(name="P1")
    db_session.add(project)
    await db_session.flush()

    item = BOQItem(
        project_id=project.id,
        description="Reinforced concrete C35/45 in columns",
        unit="m3",
        quantity=5400,
        trade_category="concrete",
    )
    db_session.add(item)
    await db_session.commit()

    from sqlalchemy import select
    got = (await db_session.execute(select(BOQItem))).scalar_one()
    assert got.description.startswith("Reinforced concrete")
    assert got.unit == "m3"
    assert got.project_id == project.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_boq.py -v`
Expected: FAIL (ModuleNotFoundError: app.models.boq).

- [ ] **Step 3: Port the model**

Read `bidops-ai/backend/app/models/boq.py`. Create `app/models/boq.py` with the `BOQItem` class, adapting:
- Import `Base, TimestampMixin` (and any enums used) from `app.models.base`.
- `from __future__ import annotations` at top; use `TYPE_CHECKING` for relationship type imports (`Project`, `Package`).
- Replace any Postgres-only column types with SQLite-friendly equivalents: `JSONB`→`JSON` (from `sqlalchemy`), `ARRAY(...)`→`JSON`.
- Preserve all columns and the `full_reference` property: `project_id`/`package_id` FKs, `line_number`, `section`, `subsection`, `description`, `description_ar`, `unit`, `quantity`, `client_ref`, `client_row_index`, `trade_category`, `classification_confidence`, `spec_references` (JSON), `unit_rate`, `total_price`, `price_source`, `selected_offer_id`, `mapping_confidence`, `requires_review`, `is_excluded`.
- Make `package_id`/`selected_offer_id` FK columns nullable (packages/offers tables are created in later tasks; for SQLite use `ForeignKey("packages.id")` etc. — the referenced tables will exist once Task 4/5 land and all are registered, so keep the FKs but ensure those tasks are applied before running the full suite). If running this task in isolation, define `package_id`/`selected_offer_id` as plain nullable `int` columns with the `ForeignKey` added in Task 4/5; simplest: include the ForeignKey strings now and complete Tasks 4–5 before the final `create_all`.

- [ ] **Step 4: Register in `app/models/__init__.py`**

Add (matching existing export style):

```python
from app.models.boq import BOQItem  # noqa: F401
```
and add `"BOQItem"` to `__all__` if present.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_boq.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models/boq.py app/models/__init__.py tests/models/test_boq.py
git commit -m "feat(models): port BOQItem model"
```

---

## Task 4: Port `Package` + `PackageDocument`

**Files:**
- Create: `app/models/package.py` (port from `bidops-ai/backend/app/models/package.py`)
- Modify: `app/models/__init__.py`
- Test: `tests/models/test_package.py`

- [ ] **Step 1: Write the failing test `tests/models/test_package.py`**

```python
async def test_package_roundtrip(db_session):
    from app.models.package import Package, PackageDocument
    from app.models.project import Project

    project = Project(name="P1")
    db_session.add(project)
    await db_session.flush()

    pkg = Package(
        project_id=project.id,
        code="PKG-P1-CONC-001",
        name="Concrete Works",
        trade_category="concrete",
        status="draft",
    )
    db_session.add(pkg)
    await db_session.commit()

    from sqlalchemy import select
    got = (await db_session.execute(select(Package))).scalar_one()
    assert got.code == "PKG-P1-CONC-001"
    assert got.project_id == project.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_package.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Port the models**

Read `bidops-ai/backend/app/models/package.py`. Create `app/models/package.py` with `Package` and `PackageDocument`, applying the same adaptation rules as Task 3 Step 3. Preserve: `Package` (code, name, trade_category, `status` as String storing `PackageStatus` value, submission_deadline, instructions, estimated_value, folder_path, brief_path, target_supplier_ids JSON, counters, relationships to project/items/linked_documents) and `PackageDocument` (package_id + document_id FKs, relevance_score, relevance_reason, sections, page_ranges, excerpt, include_in_package). Use `String` columns for enum values to match root convention, defaulting to `PackageStatus.DRAFT.value`.

- [ ] **Step 4: Register in `app/models/__init__.py`**

```python
from app.models.package import Package, PackageDocument  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_package.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models/package.py app/models/__init__.py tests/models/test_package.py
git commit -m "feat(models): port Package and PackageDocument models"
```

---

## Task 5: Port `Supplier` + `SupplierOffer`

**Files:**
- Create: `app/models/supplier.py` (port from `bidops-ai/backend/app/models/supplier.py`)
- Modify: `app/models/__init__.py`
- Test: `tests/models/test_supplier.py`

- [ ] **Step 1: Write the failing test `tests/models/test_supplier.py`**

```python
async def test_supplier_and_offer_roundtrip(db_session):
    from app.models.supplier import Supplier, SupplierOffer
    from app.models.project import Project
    from app.models.package import Package

    project = Project(name="P1")
    db_session.add(project)
    await db_session.flush()
    pkg = Package(project_id=project.id, code="PKG-1", name="X", trade_category="mep", status="draft")
    db_session.add(pkg)
    sup = Supplier(name="Carrier", code="SUP-0001", emails=["sales@carrier.test"], trade_categories=["hvac"])
    db_session.add(sup)
    await db_session.flush()

    offer = SupplierOffer(
        package_id=pkg.id, supplier_id=sup.id, status="received",
        total_price=1000000.0, currency="EGP",
    )
    db_session.add(offer)
    await db_session.commit()

    from sqlalchemy import select
    got = (await db_session.execute(select(SupplierOffer))).scalar_one()
    assert got.total_price == 1000000.0
    assert got.supplier_id == sup.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_supplier.py -v`
Expected: FAIL.

- [ ] **Step 3: Port the models**

Read `bidops-ai/backend/app/models/supplier.py` (note: `SupplierOffer` lives here, not in a separate `offer.py`). Create `app/models/supplier.py` with `Supplier` and `SupplierOffer`, applying Task 3 adaptation rules. Preserve `Supplier` (emails/trade_categories JSON, contact fields, rating, performance counters, blacklist fields, `response_rate` property) and `SupplierOffer` (status String storing `OfferStatus` value, file_paths JSON, commercial fields, AI-compliance JSON fields, scoring fields, line_items JSON, `is_compliant` property).

- [ ] **Step 4: Register in `app/models/__init__.py`**

```python
from app.models.supplier import Supplier, SupplierOffer  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_supplier.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models/supplier.py app/models/__init__.py tests/models/test_supplier.py
git commit -m "feat(models): port Supplier and SupplierOffer models"
```

---

## Task 6: Port `EmailLog`

**Files:**
- Create: `app/models/email.py` (port from `bidops-ai/backend/app/models/email.py`)
- Modify: `app/models/__init__.py`
- Test: `tests/models/test_email.py`

- [ ] **Step 1: Write the failing test `tests/models/test_email.py`**

```python
async def test_email_log_roundtrip(db_session):
    from app.models.email import EmailLog
    log = EmailLog(
        email_type="rfq", status="draft",
        to=["sales@carrier.test"], subject="[P1]-PKG-1-RFQ", body_html="<p>hi</p>",
    )
    db_session.add(log)
    await db_session.commit()
    from sqlalchemy import select
    got = (await db_session.execute(select(EmailLog))).scalar_one()
    assert got.subject.endswith("RFQ")
    assert got.status == "draft"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_email.py -v`
Expected: FAIL.

- [ ] **Step 3: Port the model**

Read `bidops-ai/backend/app/models/email.py`. Create `app/models/email.py` with `EmailLog`, applying Task 3 rules. Preserve package/supplier/offer nullable FKs, `email_type`/`status` String columns (storing `EmailType`/`EmailStatus` values), to/cc/bcc JSON, subject/body_html/body_text, attachments JSON, message/thread/conversation ids, error_message/retry_count/max_retries, timestamps, `is_sent` property.

- [ ] **Step 4: Register in `app/models/__init__.py`**

```python
from app.models.email import EmailLog  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_email.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models/email.py app/models/__init__.py tests/models/test_email.py
git commit -m "feat(models): port EmailLog model"
```

---

## Task 7: Port `AuditLog`

**Files:**
- Create: `app/models/audit.py` (port from `bidops-ai/backend/app/models/audit.py`)
- Modify: `app/models/__init__.py`
- Test: `tests/models/test_audit.py`

- [ ] **Step 1: Write the failing test `tests/models/test_audit.py`**

```python
async def test_audit_log_roundtrip(db_session):
    from app.models.audit import AuditLog
    entry = AuditLog(
        action="extraction.run", entity_type="project", entity_id="1",
        description="ran summary extraction", success=True,
    )
    db_session.add(entry)
    await db_session.commit()
    from sqlalchemy import select
    got = (await db_session.execute(select(AuditLog))).scalar_one()
    assert got.action == "extraction.run"
    assert got.success is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_audit.py -v`
Expected: FAIL.

- [ ] **Step 3: Port the model**

Read `bidops-ai/backend/app/models/audit.py`. Create `app/models/audit.py` with `AuditLog`, applying Task 3 rules. Make `user_id` FK nullable (single-user for now; users table arrives in Task 8). Preserve timestamp, user_id/user_email, action, entity_type/entity_id/entity_name, old_value/new_value JSON, description, ip_address/user_agent/request_id, success/error_message.

- [ ] **Step 4: Register in `app/models/__init__.py`**

```python
from app.models.audit import AuditLog  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_audit.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models/audit.py app/models/__init__.py tests/models/test_audit.py
git commit -m "feat(models): port AuditLog model"
```

---

## Task 8: Port `Organization` + `User`

**Files:**
- Create: `app/models/user.py` (port from `bidops-ai/backend/app/models/user.py`)
- Modify: `app/models/__init__.py`
- Test: `tests/models/test_user.py`

- [ ] **Step 1: Write the failing test `tests/models/test_user.py`**

```python
async def test_user_and_org_roundtrip(db_session):
    from app.models.user import User, Organization
    org = Organization(name="Acme Contracting", code="ACME")
    db_session.add(org)
    await db_session.flush()
    user = User(
        email="est@acme.test", hashed_password="x", full_name="Est",
        role="estimator", organization_id=org.id,
    )
    db_session.add(user)
    await db_session.commit()
    from sqlalchemy import select
    got = (await db_session.execute(select(User))).scalar_one()
    assert got.email == "est@acme.test"
    assert got.role == "estimator"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_user.py -v`
Expected: FAIL.

- [ ] **Step 3: Port the models**

Read `bidops-ai/backend/app/models/user.py`. Create `app/models/user.py` with `Organization` and `User`, applying Task 3 rules. `role` is a String column storing `UserRole` value. Preserve org (name/code/settings JSON/is_active) and user (email unique+indexed, hashed_password, full_name, role, organization_id FK, is_active/is_verified/last_login).

- [ ] **Step 4: Register in `app/models/__init__.py`**

```python
from app.models.user import Organization, User  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/models/test_user.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models/user.py app/models/__init__.py tests/models/test_user.py
git commit -m "feat(models): port Organization and User models"
```

---

## Task 9: Full-suite + all-tables integration check

**Files:**
- Create: `tests/models/test_all_tables.py`

- [ ] **Step 1: Write the test**

```python
async def test_all_v2_tables_created(db_session):
    from sqlalchemy import text
    rows = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    names = {r[0] for r in rows}
    for expected in [
        "boq_items", "packages", "package_documents", "suppliers",
        "supplier_offers", "email_logs", "audit_logs", "users", "organizations",
    ]:
        assert expected in names, f"missing table: {expected}"
```

Note: if a `__tablename__` differs from the guess above, align the assertion to the actual `__tablename__` from the ported model (do not rename the model's table).

- [ ] **Step 2: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all tests PASS (harness + enums + 7 model groups + all-tables). Resolves any cross-model FK/relationship issues now that every table is registered.

- [ ] **Step 3: Commit**

```bash
git add tests/models/test_all_tables.py
git commit -m "test(models): assert all v2 domain tables are created"
```

---

## Task 10: Alembic migration for the v2 tables

**Files:**
- Create: `migrations/versions/<rev>_v2_domain_models.py` (autogenerated)

- [ ] **Step 1: Verify alembic env imports the models' metadata**

Read `migrations/env.py`. Confirm `target_metadata` is `app.models.Base.metadata` (so all newly-registered models are visible). If it imports a specific metadata, ensure the new models are imported there. If `app.models` is already imported, no change needed.

- [ ] **Step 2: Autogenerate the migration**

Run: `.venv/Scripts/python.exe -m alembic revision --autogenerate -m "v2 domain models"`
Expected: a new file in `migrations/versions/` with `op.create_table(...)` for boq_items, packages, package_documents, suppliers, supplier_offers, email_logs, audit_logs, users, organizations.

- [ ] **Step 3: Inspect the generated migration**

Open the new file. Verify it only ADDS the 9 new tables (no drops of `projects`/`documents`). Remove any spurious drops/alters if present.

- [ ] **Step 4: Apply and verify**

Run: `.venv/Scripts/python.exe -m alembic upgrade head`
Expected: completes without error; `data/bidops.db` now contains the new tables.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/
git commit -m "feat(db): alembic migration adding v2 domain tables"
```

---

## Self-Review (completed by author)

- **Spec coverage:** Implements the "port 7 models + migration" half of Phase 6 (Foundation) from the v2 design spec. Models: BOQItem, Package, PackageDocument, Supplier, SupplierOffer, EmailLog, AuditLog, User, Organization — all covered. Test harness (a stated NFR: "test scaffolding established in P6") covered in Task 1.
- **Out of scope (sibling plans):** rules/market config system (6B), React SPA (6C). Noted in header.
- **Placeholder scan:** Model bodies are "port from named source + explicit adaptation rules + full verification test" — actionable for a port (the source is in-repo). Harness/enums/registration/tests have complete code.
- **Type consistency:** Enum columns stored as `String` values consistently (matches root app's `ProjectStatus`/`DocumentStatus` convention). `db_session` fixture name consistent across all test files. Table-name assertions flagged to align with actual `__tablename__`.
- **Dependency note:** Tasks 3–8 add cross-table FKs; Task 9 runs the full suite once all tables are registered to catch any FK ordering issues. This is intentional.
