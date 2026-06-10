# Phase 7C — Document Classification + Addenda-Supersedes Versioning + Dedup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every project document into a tender category (ITT/specs/BOQ/drawings/contract/addendum/…), detect exact duplicates by content hash, detect filename revision chains (Rev A → Rev B, v1 → v2) and mark older versions superseded — so the packaging document-linker never attaches a superseded/duplicate document to a package — with a manual override and visible badges in the UI.

**Architecture:** Deterministic, no LLM. One additive migration on `documents` (category, content_hash, is_superseded, superseded_by_id, version_label, supersede_reason). A rules-driven keyword classifier (`doc_classifier.py` — keywords live in a new `classification.document_categories` rules section, precedence = JSON order, addendum first). `VersioningService.analyze()` is idempotent: it resets only auto-applied marks (reasons prefixed `auto:`), preserving manual ones, then (a) hashes file bytes (fallback: extracted text), (b) marks hash-duplicates superseded by the earliest copy, (c) parses filename version tokens to group revision chains and marks all but the newest superseded, (d) re-classifies every document. `DocumentLinker` (the money path) skips hits from superseded documents. Manual `PATCH /api/documents/{id}/supersede` covers true cross-document addenda judgment a filename heuristic cannot make. The v1 documents table gains Category/Version columns and an "Analyze versions" button.

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + Alembic (one additive migration, head `c7e1a2f3b4d5` → new) · stdlib `hashlib`/`re` · Jinja (one template edit) · pytest-asyncio + httpx ASGITransport.

---

## Pre-flight (read, do not skip)

1. **Migration discipline:** new columns only (no new table). Use `op.batch_alter_table("documents")` with `add_column` (SQLite-safe). `superseded_by_id` is a plain indexed `Integer` (NO FK constraint — adding FKs to an existing SQLite table forces a table rebuild and FKs aren't enforced anyway; document this in the migration docstring). `down_revision = 'c7e1a2f3b4d5'`.
2. **Three-place model registration does NOT apply** (no new model) — `Document` is already registered everywhere; only columns are added.
3. **Rules:** new `Classification` section must be default-constructible (`default_factory=dict`) and added to `config/rules.default.json`. JSON insertion order defines match precedence — keep `addendum` FIRST (an "Addendum 3 — revised specs.pdf" is an addendum, not specs).
4. **`auto:` reason convention is the idempotency key.** `analyze()` resets ONLY rows whose `supersede_reason` starts with `auto:` — manual marks (any other reason) survive re-analysis, and manually-superseded docs are never chosen as chain keepers.
5. **DocumentLinker exclusion** is the protection that matters (packages → RFQs → pricing all flow from linked docs). Filter superseded doc ids inside `link_package`. Do NOT touch the v1 search/extraction services (out of scope; superseded docs remaining in semantic search context is a documented limitation).
6. **Order chains by `(version_rank, id)`** — newest rank wins; rank ties go to the later upload (`id` encodes upload order). Do NOT use `created_at` in the sort key (it can be None pre-commit, and mixing datetime/int raises TypeError).
7. Root conventions: services take `db: AsyncSession`; enums stored as `.value` strings (`DocumentCategory`); responses from explicit queries.

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (baseline = **271 passing**).

---

## File Structure

**Create:**
- `migrations/versions/d4f8b2c9e1a7_document_versioning.py`
- `app/services/versioning/__init__.py`
- `app/services/versioning/doc_classifier.py` — `classify_document(filename, text, rules) -> (category, confidence)`
- `app/services/versioning/versioning_service.py` — `parse_version`, `VersioningService` (analyze, mark_superseded, unmark_superseded)
- `app/api/versioning.py` — analyze + manual supersede endpoints
- `tests/versioning/__init__.py`, `test_classifier.py`, `test_parse_version.py`, `test_versioning_service.py`, `test_versioning_api.py`

**Modify:**
- `app/models/document.py` — 6 new columns.
- `app/schemas/document.py` — expose new fields on `DocumentResponse`.
- `app/schemas/rules.py` + `config/rules.default.json` — `classification.document_categories`.
- `app/services/packaging/document_linker.py` — skip superseded docs.
- `app/api/documents.py` or `app/main.py` — register the new router (`app/main.py`).
- `app/templates/project.html` — Category/Version columns + Analyze button.
- `tests/ui/test_pages.py` — marker test.
- `tests/packaging/test_document_linker.py` — exclusion test.

---

## Task 1: Model columns + migration + response schema

**Files:**
- Modify: `app/models/document.py`, `app/schemas/document.py`
- Create: `migrations/versions/d4f8b2c9e1a7_document_versioning.py`
- Test: `tests/versioning/__init__.py`, `tests/versioning/test_versioning_service.py` (first test only)

- [ ] **Step 1: Write the failing test**

Create `tests/versioning/__init__.py` (empty file).

Create `tests/versioning/test_versioning_service.py`:

```python
import pytest
from sqlalchemy import select

from app.models.document import Document


async def test_document_versioning_columns_persist(db_session):
    doc = Document(
        project_id=1, filename="Spec_RevB.pdf", file_path="/t/s.pdf",
        file_type="pdf", file_size=1,
        category="specs", content_hash="ab" * 32,
        is_superseded=True, superseded_by_id=99,
        version_label="rev B", supersede_reason="auto:test",
    )
    db_session.add(doc)
    await db_session.commit()
    got = (await db_session.execute(select(Document))).scalar_one()
    assert got.category == "specs"
    assert got.is_superseded is True
    assert got.superseded_by_id == 99
    assert got.version_label == "rev B"
    assert got.supersede_reason == "auto:test"
```

Run: `.venv/Scripts/python.exe -m pytest tests/versioning/ -q` → FAIL (`TypeError: 'category' is an invalid keyword argument`).

- [ ] **Step 2: Add the columns to `app/models/document.py`**

After the `processing_time_ms` column and before `created_at`, add:

```python
    # Classification + versioning (Phase 7C). category holds a DocumentCategory
    # value string; supersede_reason values starting with "auto:" are owned by
    # VersioningService.analyze() and reset on re-analysis — any other reason is
    # a manual mark and survives.
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    is_superseded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    superseded_by_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    version_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supersede_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Add `Boolean` to the existing `from sqlalchemy import ...` line.

- [ ] **Step 3: Write the migration**

Create `migrations/versions/d4f8b2c9e1a7_document_versioning.py`:

```python
"""document classification + versioning columns

Revision ID: d4f8b2c9e1a7
Revises: c7e1a2f3b4d5
Create Date: 2026-06-10 12:00:00.000000

Additive columns for Phase 7C (classification, content-hash dedup,
addenda-supersedes versioning). superseded_by_id is intentionally a plain
indexed Integer (no FK): SQLite cannot add an FK to an existing table without
a full rebuild, and FK enforcement is off anyway.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f8b2c9e1a7'
down_revision: Union[str, None] = 'c7e1a2f3b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("category", sa.String(length=20), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("superseded_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("version_label", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("supersede_reason", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_documents_content_hash"), "documents", ["content_hash"])
    op.create_index(op.f("ix_documents_superseded_by_id"), "documents", ["superseded_by_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_superseded_by_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_content_hash"), table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("supersede_reason")
        batch.drop_column("version_label")
        batch.drop_column("superseded_by_id")
        batch.drop_column("is_superseded")
        batch.drop_column("content_hash")
        batch.drop_column("category")
```

- [ ] **Step 4: Expose the fields on `DocumentResponse`** (`app/schemas/document.py`)

Add after `error_message: str | None`:

```python
    category: str = "unknown"
    is_superseded: bool = False
    superseded_by_id: int | None = None
    version_label: str | None = None
    supersede_reason: str | None = None
```

- [ ] **Step 5: Verify**

Run: `.venv/Scripts/python.exe -m pytest tests/versioning/ -q` → PASS. Then `.venv/Scripts/python.exe -m alembic heads` → single head `d4f8b2c9e1a7`. Full suite green.

- [ ] **Step 6: Commit**

```bash
git add app/models/document.py app/schemas/document.py migrations/versions/d4f8b2c9e1a7_document_versioning.py tests/versioning/
git commit -m "feat(phase-7c): document classification/versioning columns + migration"
```

---

## Task 2: Rules section + keyword classifier

**Files:**
- Modify: `app/schemas/rules.py`, `config/rules.default.json`
- Create: `app/services/versioning/__init__.py`, `app/services/versioning/doc_classifier.py`
- Test: `tests/versioning/test_classifier.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/versioning/test_classifier.py`:

```python
from app.schemas.rules import RulesConfig
from app.services.rules.rules_service import RulesService
from app.services.versioning.doc_classifier import classify_document


def _rules():
    return RulesService().load()  # real defaults from config/rules.default.json


def test_filename_classification():
    rules = _rules()
    assert classify_document("Addendum_03_Revised_Specs.pdf", "", rules)[0] == "addendum"
    assert classify_document("BOQ_Bill_of_Quantities.xlsx", "", rules)[0] == "boq"
    assert classify_document("Architectural Drawings Pkg.pdf", "", rules)[0] == "drawings"
    assert classify_document("Conditions_of_Contract.docx", "", rules)[0] == "contract"
    assert classify_document("Instructions to Tenderers.pdf", "", rules)[0] == "itt"
    assert classify_document("Mechanical_Specifications.pdf", "", rules)[0] == "specs"


def test_filename_match_has_high_confidence():
    cat, conf = classify_document("Tender BOQ final.xlsx", "", _rules())
    assert cat == "boq"
    assert conf >= 0.9


def test_text_fallback_classification():
    cat, conf = classify_document(
        "document_017.pdf",
        "This bill of quantities lists all measured works ...",
        _rules(),
    )
    assert cat == "boq"
    assert 0 < conf < 0.9


def test_no_match_returns_general():
    cat, conf = classify_document("scan_001.pdf", "lorem ipsum", _rules())
    assert cat == "general"
    assert conf == 0.0


def test_keywords_are_configurable():
    cfg = RulesConfig()
    cfg.classification.document_categories = {"hse": ["safety dossier"]}
    class _Fake:
        def load(self):
            return cfg
    cat, _ = classify_document("Project Safety Dossier.pdf", "", _Fake().load())
    assert cat == "hse"
```

Run: `.venv/Scripts/python.exe -m pytest tests/versioning/test_classifier.py -q` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Add the rules section**

In `app/schemas/rules.py`, add before `class RulesConfig`:

```python
class Classification(BaseModel):
    """Keyword → document-category mapping. Dict order = match precedence."""

    document_categories: dict[str, list[str]] = Field(default_factory=dict)
```

Add to `RulesConfig`:

```python
    classification: Classification = Field(default_factory=Classification)
```

In `config/rules.default.json`, add a top-level `"classification"` key (order matters — addendum first):

```json
  "classification": {
    "document_categories": {
      "addendum": ["addendum", "addenda", "amendment", "bulletin", "ملحق"],
      "boq": ["boq", "bill of quantities", "bills of quantities", "pricing schedule", "جداول الكميات"],
      "drawings": ["drawing", "drawings", "dwg", "plan layout", "المخططات"],
      "contract": ["contract", "agreement", "conditions of contract", "العقد"],
      "itt": ["itt", "invitation to tender", "instructions to tenderers", "instruction to bidders", "rfp"],
      "schedule": ["programme", "program of works", "schedule of works", "primavera", "gantt"],
      "hse": ["hse", "health and safety", "safety plan", "environmental plan"],
      "correspondence": ["letter", "correspondence", "minutes of meeting", "mom", "email"],
      "specs": ["specification", "specifications", "specs", "technical requirements", "المواصفات"]
    }
  },
```

(Place it after the `"keywords"` section; keep valid JSON commas.)

- [ ] **Step 3: Implement the classifier**

Create `app/services/versioning/__init__.py` (empty file).

Create `app/services/versioning/doc_classifier.py`:

```python
"""Rule-based document classifier: filename keywords first, text fallback.

Keywords come from rules.classification.document_categories; dict order is
match precedence (addendum is listed first so 'Addendum 3 - revised specs'
classifies as addendum, not specs). Deterministic — no LLM.
"""

from __future__ import annotations

_FILENAME_CONFIDENCE = 0.9
_TEXT_CONFIDENCE = 0.6
_TEXT_SAMPLE_CHARS = 2000


def classify_document(filename: str, text: str | None, rules) -> tuple[str, float]:
    """Return (category, confidence). 'general' / 0.0 when nothing matches."""
    categories = rules.classification.document_categories
    name = (filename or "").lower()
    for category, keywords in categories.items():
        if any(kw.lower() in name for kw in keywords):
            return category, _FILENAME_CONFIDENCE
    sample = (text or "")[:_TEXT_SAMPLE_CHARS].lower()
    if sample:
        for category, keywords in categories.items():
            if any(kw.lower() in sample for kw in keywords):
                return category, _TEXT_CONFIDENCE
    return "general", 0.0
```

- [ ] **Step 4: Run tests; commit**

`.venv/Scripts/python.exe -m pytest tests/versioning/ tests/services/ tests/api/ -q` → PASS (rules schema/API tests must still pass — the new section is additive with defaults). Full suite green.

```bash
git add app/schemas/rules.py config/rules.default.json app/services/versioning/ tests/versioning/test_classifier.py
git commit -m "feat(phase-7c): rules-driven document category classifier"
```

---

## Task 3: Version parsing + VersioningService.analyze

**Files:**
- Create: `app/services/versioning/versioning_service.py`
- Test: `tests/versioning/test_parse_version.py`, `tests/versioning/test_versioning_service.py` (append)

- [ ] **Step 1: Write the failing tests**

Create `tests/versioning/test_parse_version.py`:

```python
from app.services.versioning.versioning_service import parse_version


def test_rev_letter():
    base, rank, label = parse_version("Mechanical_Spec_RevB.pdf")
    assert rank == 2
    assert label == "rev B"
    base_a, rank_a, _ = parse_version("Mechanical_Spec_RevA.pdf")
    assert base == base_a
    assert rank > rank_a


def test_rev_number_and_v_number():
    assert parse_version("BOQ rev 2.xlsx")[1] == 2
    assert parse_version("BOQ_v3.xlsx")[1] == 3
    assert parse_version("Contract issue 2.docx")[1] == 2


def test_same_base_across_styles():
    b1, _, _ = parse_version("Spec_Rev A.pdf")
    b2, _, _ = parse_version("Spec rev.B.pdf")
    assert b1 == b2


def test_no_token_rank_zero():
    base, rank, label = parse_version("Specifications.pdf")
    assert rank == 0
    assert label is None
    # base of un-versioned file groups with versioned siblings
    vb, _, _ = parse_version("Specifications Rev A.pdf")
    assert base == vb


def test_unrelated_names_do_not_collide():
    assert parse_version("BOQ_v2.xlsx")[0] != parse_version("Drawings_v2.pdf")[0]
```

Append to `tests/versioning/test_versioning_service.py`:

```python
from pathlib import Path

from app.models.project import Project
from app.services.versioning.versioning_service import VersioningService


async def _seed_project(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    return project.id


def _doc(pid, filename, path="/missing", text=None, **kw):
    return Document(project_id=pid, filename=filename, file_path=path,
                    file_type=Path(filename).suffix.lstrip(".") or "pdf",
                    file_size=1, extracted_text=text, **kw)


async def test_analyze_marks_duplicates_by_content(db_session, tmp_path):
    pid = await _seed_project(db_session)
    f1 = tmp_path / "a.pdf"; f1.write_bytes(b"SAME BYTES")
    f2 = tmp_path / "b.pdf"; f2.write_bytes(b"SAME BYTES")
    d1 = _doc(pid, "Original.pdf", str(f1))
    d2 = _doc(pid, "Copy of Original.pdf", str(f2))
    db_session.add_all([d1, d2])
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    assert result["duplicates"] == 1
    await db_session.refresh(d2)
    assert d2.is_superseded is True
    assert d2.superseded_by_id == d1.id
    assert d2.supersede_reason.startswith("auto:duplicate")
    await db_session.refresh(d1)
    assert d1.is_superseded is False


async def test_analyze_marks_older_revisions(db_session):
    pid = await _seed_project(db_session)
    old = _doc(pid, "Spec_RevA.pdf", text="specification rev a")
    new = _doc(pid, "Spec_RevB.pdf", text="specification rev b")
    db_session.add_all([old, new])
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    assert result["superseded"] == 1
    await db_session.refresh(old)
    await db_session.refresh(new)
    assert old.is_superseded is True
    assert old.superseded_by_id == new.id
    assert "newer revision" in old.supersede_reason
    assert new.is_superseded is False
    assert new.version_label == "rev B"


async def test_analyze_classifies_documents(db_session):
    pid = await _seed_project(db_session)
    d = _doc(pid, "Addendum_01.pdf", text="addendum to the tender")
    db_session.add(d)
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    await db_session.refresh(d)
    assert d.category == "addendum"
    assert result["by_category"]["addendum"] == 1


async def test_analyze_is_idempotent_and_preserves_manual_marks(db_session):
    pid = await _seed_project(db_session)
    a = _doc(pid, "Spec_RevA.pdf", text="x")
    b = _doc(pid, "Spec_RevB.pdf", text="y")
    manual = _doc(pid, "Old base ITT.pdf", text="itt")
    db_session.add_all([a, b, manual])
    await db_session.commit()
    svc = VersioningService()
    await svc.analyze(db_session, pid)
    # manual mark with a human reason
    await svc.mark_superseded(db_session, manual.id, superseded_by_id=b.id,
                              reason="replaced by addendum 2 (manual)")
    # re-analyze: auto marks recomputed, manual mark must survive
    result2 = await svc.analyze(db_session, pid)
    await db_session.refresh(manual)
    assert manual.is_superseded is True
    assert manual.supersede_reason == "replaced by addendum 2 (manual)"
    await db_session.refresh(a)
    assert a.is_superseded is True  # auto mark re-applied
    assert result2["superseded"] == 1


async def test_unmark_superseded(db_session):
    pid = await _seed_project(db_session)
    d = _doc(pid, "Doc.pdf")
    db_session.add(d)
    await db_session.commit()
    svc = VersioningService()
    await svc.mark_superseded(db_session, d.id, superseded_by_id=None, reason="mistake")
    await db_session.refresh(d)
    assert d.is_superseded is True
    await svc.unmark_superseded(db_session, d.id)
    await db_session.refresh(d)
    assert d.is_superseded is False
    assert d.supersede_reason is None
```

Run: FAIL (`ModuleNotFoundError: ...versioning_service`).

- [ ] **Step 2: Implement the service**

Create `app/services/versioning/versioning_service.py`:

```python
"""Content-hash dedup + filename revision chains + classification.

analyze() is idempotent: it resets ONLY auto-applied marks (supersede_reason
starting with "auto:") and re-derives them; manual marks survive and manually
superseded documents are never selected as chain keepers. Deterministic — no
LLM. True cross-document addenda judgment (e.g. "Addendum 2 replaces section 5
of the ITT") is a human call: use mark_superseded for it.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.rules.rules_service import RulesService
from app.services.versioning.doc_classifier import classify_document

# Filename version tokens, tried in order. Each yields (rank, label).
_VERSION_PATTERNS = (
    ("rev", re.compile(r"(?:^|[\s_\-.])rev(?:ision)?[\s_\-.]*([a-z]|\d{1,3})(?=[\s_\-.)(]|$)", re.I)),
    ("v", re.compile(r"(?:^|[\s_\-.])v(?:er(?:sion)?)?[\s_\-.]*(\d{1,3})(?=[\s_\-.)(]|$)", re.I)),
    ("issue", re.compile(r"(?:^|[\s_\-.])issue[\s_\-.]*(\d{1,3})(?=[\s_\-.)(]|$)", re.I)),
)


def _normalize_base(stem: str) -> str:
    return re.sub(r"[^\w]+", "_", stem.lower()).strip("_")


def parse_version(filename: str) -> tuple[str, int, str | None]:
    """Return (base_key, rank, label). rank 0 / label None when no token found.

    The base_key strips the version token so 'Spec_RevA.pdf' and
    'Spec rev.B.pdf' share a base and form one revision chain.
    """
    stem = Path(filename).stem
    for kind, pattern in _VERSION_PATTERNS:
        m = pattern.search(stem)
        if m:
            token = m.group(1)
            rank = (ord(token.lower()) - ord("a") + 1) if token.isalpha() else int(token)
            base = stem[: m.start()] + " " + stem[m.end():]
            return _normalize_base(base), rank, f"{kind} {token.upper()}"
    return _normalize_base(stem), 0, None


def _hash_document(doc: Document) -> str | None:
    path = Path(doc.file_path)
    if path.exists() and path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if doc.extracted_text:
        return hashlib.sha256(doc.extracted_text.encode("utf-8")).hexdigest()
    return None


class VersioningService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    async def analyze(self, db: AsyncSession, project_id: int) -> dict:
        rules = self._rules_service.load()

        # Reset ONLY auto marks; manual marks survive re-analysis.
        await db.execute(
            update(Document)
            .where(
                Document.project_id == project_id,
                Document.supersede_reason.like("auto:%"),
            )
            .values(is_superseded=False, superseded_by_id=None, supersede_reason=None)
        )

        docs = list(
            (
                await db.execute(
                    select(Document)
                    .where(Document.project_id == project_id)
                    .order_by(Document.id)
                )
            ).scalars().all()
        )

        # 1) Classify everything + ensure hashes + version labels.
        by_category: dict[str, int] = defaultdict(int)
        for doc in docs:
            category, _conf = classify_document(doc.filename, doc.extracted_text, rules)
            doc.category = category
            by_category[category] += 1
            if not doc.content_hash:
                doc.content_hash = _hash_document(doc)
            _base, _rank, label = parse_version(doc.filename)
            doc.version_label = label

        manual_superseded = {
            d.id for d in docs
            if d.is_superseded and not (d.supersede_reason or "").startswith("auto:")
        }
        candidates = [d for d in docs if d.id not in manual_superseded]

        # 2) Exact duplicates by content hash — keep the EARLIEST copy.
        duplicates = 0
        groups: dict[str, list[Document]] = defaultdict(list)
        for doc in candidates:
            if doc.content_hash:
                groups[doc.content_hash].append(doc)
        duplicate_ids: set[int] = set()
        for group in groups.values():
            if len(group) < 2:
                continue
            keeper = min(group, key=lambda d: d.id)
            for doc in group:
                if doc.id == keeper.id:
                    continue
                doc.is_superseded = True
                doc.superseded_by_id = keeper.id
                doc.supersede_reason = f"auto:duplicate of #{keeper.id}"
                duplicate_ids.add(doc.id)
                duplicates += 1

        # 3) Revision chains by (base_key, file_type) — newest rank wins.
        superseded = 0
        chains: dict[tuple[str, str], list[tuple[Document, int]]] = defaultdict(list)
        for doc in candidates:
            if doc.id in duplicate_ids:
                continue
            base, rank, _label = parse_version(doc.filename)
            chains[(base, doc.file_type)].append((doc, rank))
        for members in chains.values():
            if len(members) < 2 or not any(rank > 0 for _d, rank in members):
                continue  # need 2+ docs and at least one explicit version token
            # id encodes upload order (created_at can be None pre-commit and
            # mixing datetime/int in a sort key raises TypeError).
            members.sort(key=lambda dr: (dr[1], dr[0].id))
            keeper = members[-1][0]
            for doc, _rank in members[:-1]:
                doc.is_superseded = True
                doc.superseded_by_id = keeper.id
                doc.supersede_reason = f"auto:superseded by #{keeper.id} (newer revision)"
                superseded += 1

        await db.commit()
        return {
            "project_id": project_id,
            "documents": len(docs),
            "duplicates": duplicates,
            "superseded": superseded,
            "by_category": dict(by_category),
        }

    async def mark_superseded(
        self,
        db: AsyncSession,
        document_id: int,
        *,
        superseded_by_id: int | None,
        reason: str,
    ) -> Document | None:
        doc = await db.get(Document, document_id)
        if doc is None:
            return None
        doc.is_superseded = True
        doc.superseded_by_id = superseded_by_id
        doc.supersede_reason = reason or "manually superseded"
        await db.commit()
        await db.refresh(doc)
        return doc

    async def unmark_superseded(self, db: AsyncSession, document_id: int) -> Document | None:
        doc = await db.get(Document, document_id)
        if doc is None:
            return None
        doc.is_superseded = False
        doc.superseded_by_id = None
        doc.supersede_reason = None
        await db.commit()
        await db.refresh(doc)
        return doc
```

- [ ] **Step 3: Run tests; commit**

`.venv/Scripts/python.exe -m pytest tests/versioning/ -q` → PASS. Full suite green.

```bash
git add app/services/versioning/versioning_service.py tests/versioning/test_parse_version.py tests/versioning/test_versioning_service.py
git commit -m "feat(phase-7c): VersioningService — hash dedup, revision chains, idempotent analyze"
```

---

## Task 4: API endpoints + DocumentLinker exclusion

**Files:**
- Create: `app/api/versioning.py`
- Modify: `app/main.py`, `app/services/packaging/document_linker.py`
- Test: `tests/versioning/test_versioning_api.py`, `tests/packaging/test_document_linker.py` (append)

- [ ] **Step 1: Write the failing tests**

Create `tests/versioning/test_versioning_api.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def ver_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.document import Document
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
            Document(project_id=project.id, filename="Spec_RevA.pdf", file_path="/m",
                     file_type="pdf", file_size=1, extracted_text="specification a"),
            Document(project_id=project.id, filename="Spec_RevB.pdf", file_path="/m",
                     file_type="pdf", file_size=1, extracted_text="specification b"),
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


async def test_analyze_endpoint(ver_client):
    client, pid = ver_client
    async with client as c:
        r = await c.post(f"/api/projects/{pid}/documents/analyze")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["superseded"] == 1
        assert body["by_category"]["specs"] == 2

        docs = (await c.get(f"/api/projects/{pid}/documents")).json()
        rev_a = next(d for d in docs if d["filename"] == "Spec_RevA.pdf")
        assert rev_a["is_superseded"] is True
        assert rev_a["category"] == "specs"
        assert rev_a["version_label"] == "rev A"


async def test_analyze_404_missing_project(ver_client):
    client, _ = ver_client
    async with client as c:
        r = await c.post("/api/projects/999999/documents/analyze")
    assert r.status_code == 404


async def test_manual_supersede_and_undo(ver_client):
    client, pid = ver_client
    async with client as c:
        docs = (await c.get(f"/api/projects/{pid}/documents")).json()
        target = docs[0]["id"]
        r = await c.patch(f"/api/documents/{target}/supersede",
                          json={"reason": "replaced by addendum (manual)"})
        assert r.status_code == 200
        assert r.json()["is_superseded"] is True

        undo = await c.patch(f"/api/documents/{target}/supersede", json={"undo": True})
        assert undo.status_code == 200
        assert undo.json()["is_superseded"] is False

        assert (await c.patch("/api/documents/999999/supersede", json={})).status_code == 404
```

> The `GET /api/projects/{pid}/documents` list endpoint already exists in `app/api/documents.py` and returns `DocumentResponse` — the new fields flow automatically from Task 1.

Append to `tests/packaging/test_document_linker.py` (it already has a `FakeSearch`/hit pattern in `tests/packaging/test_packaging_api.py`; this file tests the linker directly — follow its existing fixtures; if it lacks a seeded-doc helper, use the pattern below):

```python
async def test_link_package_skips_superseded_documents(db_session):
    from dataclasses import dataclass

    from app.models.boq import BOQItem
    from app.models.document import Document
    from app.models.package import Package, PackageDocument
    from app.models.project import Project
    from app.services.packaging.document_linker import DocumentLinker
    from sqlalchemy import select

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-1", trade_category="mep")
    db_session.add(package)
    live = Document(project_id=project.id, filename="Spec_RevB.pdf", file_path="/m",
                    file_type="pdf", file_size=1)
    stale = Document(project_id=project.id, filename="Spec_RevA.pdf", file_path="/m",
                     file_type="pdf", file_size=1, is_superseded=True,
                     supersede_reason="auto:superseded by newer revision")
    db_session.add_all([live, stale])
    await db_session.flush()
    db_session.add(BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                           description="AC unit", unit="no", quantity=1,
                           client_row_index=2, trade_category="mep"))
    await db_session.commit()

    @dataclass
    class Hit:
        document_id: int
        score: float
        text: str
        page_number: int = 1

    class FakeSearch:
        def search(self, project_id, query, top_k=10, mode="hybrid"):
            return [Hit(live.id, 0.9, "live spec"), Hit(stale.id, 0.95, "stale spec")]

    linker = DocumentLinker(search_service=FakeSearch())
    created = await linker.link_package(db_session, package)
    assert created == 1
    links = (await db_session.execute(
        select(PackageDocument).where(PackageDocument.package_id == package.id)
    )).scalars().all()
    assert [l.document_id for l in links] == [live.id]  # stale doc excluded
```

Run: FAIL (endpoints 404; linker links both docs).

- [ ] **Step 2: Implement the router**

Create `app/api/versioning.py`:

```python
"""Document versioning API: analyze (classify + dedup + supersede) and manual
supersede control."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.document import DocumentResponse
from app.services.versioning.versioning_service import VersioningService

router = APIRouter(tags=["versioning"])


class AnalyzeResult(BaseModel):
    project_id: int
    documents: int
    duplicates: int
    superseded: int
    by_category: dict[str, int]


class SupersedeRequest(BaseModel):
    superseded_by_id: int | None = None
    reason: str | None = None
    undo: bool = False


@router.post("/projects/{project_id}/documents/analyze", response_model=AnalyzeResult)
async def analyze_documents(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> AnalyzeResult:
    """Classify all documents, mark exact duplicates and older revisions."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    result = await VersioningService().analyze(db, project_id)
    return AnalyzeResult(**result)


@router.patch("/documents/{document_id}/supersede", response_model=DocumentResponse)
async def supersede_document(
    document_id: int, payload: SupersedeRequest, db: AsyncSession = Depends(get_db)
) -> DocumentResponse:
    """Manually mark (or unmark with undo=true) a document as superseded —
    for cross-document addenda judgment the filename heuristic cannot make."""
    svc = VersioningService()
    if payload.undo:
        doc = await svc.unmark_superseded(db, document_id)
    else:
        doc = await svc.mark_superseded(
            db, document_id,
            superseded_by_id=payload.superseded_by_id,
            reason=payload.reason or "manually superseded",
        )
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return DocumentResponse.model_validate(doc)
```

Register in `app/main.py` (import + `app.include_router(versioning_router, prefix="/api")` after the deliverables router).

- [ ] **Step 3: Exclude superseded docs in `DocumentLinker.link_package`**

In `app/services/packaging/document_linker.py`, add `from app.models.document import Document` to the imports. In `link_package`, right after the `hits = ...` try/except block and BEFORE the aggregation loop, add:

```python
        # Never link superseded/duplicate documents — pricing must flow from
        # the latest revision only (Phase 7C).
        superseded_ids = set(
            (
                await db.execute(
                    select(Document.id).where(
                        Document.project_id == package.project_id,
                        Document.is_superseded.is_(True),
                    )
                )
            ).scalars().all()
        )
```

And in the aggregation loop, after `doc_id = getattr(h, "document_id", None)` / the `None` check, add:

```python
            if doc_id in superseded_ids:
                continue
```

- [ ] **Step 4: Run tests; commit**

`.venv/Scripts/python.exe -m pytest tests/versioning/ tests/packaging/ -q` → PASS. Full suite green.

```bash
git add app/api/versioning.py app/main.py app/services/packaging/document_linker.py tests/versioning/test_versioning_api.py tests/packaging/test_document_linker.py
git commit -m "feat(phase-7c): analyze + manual supersede endpoints; linker skips superseded docs"
```

---

## Task 5: UI — Category/Version columns + Analyze button

**Files:**
- Modify: `app/templates/project.html`
- Test: `tests/ui/test_pages.py` (append)

- [ ] **Step 1: Failing test**

Append to `tests/ui/test_pages.py`:

```python
async def test_project_page_has_versioning_controls(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}")
        assert "analyzeVersions" in r.text
        # the documents table renders Category/Version headers when docs exist;
        # with no docs the empty state shows — the button must exist regardless
        assert "Analyze versions" in r.text
```

Run → FAIL.

- [ ] **Step 2: Edit `app/templates/project.html`**

(a) Replace the documents-table header block:

```html
                <tr>
                    <th>Filename</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Pages</th>
                    <th>Time</th>
                </tr>
```

with:

```html
                <tr>
                    <th>Filename</th>
                    <th>Category</th>
                    <th>Version</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Pages</th>
                    <th>Time</th>
                </tr>
```

(b) Replace the row cells `<td>{{ doc.filename }}</td>` + `<td>{{ doc.file_type }}</td>` with:

```html
                    <td>{{ doc.filename }}
                        {% if doc.is_superseded %}
                        <span class="badge badge-failed" title="{{ doc.supersede_reason }}">superseded</span>
                        {% endif %}
                    </td>
                    <td>{{ doc.category if doc.category else '-' }}</td>
                    <td>{{ doc.version_label if doc.version_label else '-' }}</td>
                    <td>{{ doc.file_type }}</td>
```

(c) Right after the `<h3 class="section-title">Documents</h3>` line, add:

```html
        <p class="action-bar">
            <button class="btn btn-secondary" type="button" onclick="analyzeVersions()">Analyze versions</button>
            <span id="analyze-result"></span>
        </p>
        <script>
        async function analyzeVersions() {
            var resp = await fetch('/api/projects/{{ project.id }}/documents/analyze', { method: 'POST' });
            if (!resp.ok) { alert('Analyze failed: ' + resp.status); return; }
            var r = await resp.json();
            document.getElementById('analyze-result').textContent =
                r.documents + ' docs — ' + r.duplicates + ' duplicates, '
                + r.superseded + ' superseded';
            setTimeout(function () { location.reload(); }, 600);
        }
        </script>
```

- [ ] **Step 3: Run tests; commit**

`.venv/Scripts/python.exe -m pytest tests/ui/ -q` → PASS. Full suite green.

```bash
git add app/templates/project.html tests/ui/test_pages.py
git commit -m "feat(phase-7c): documents table shows category/version + Analyze button"
```

---

## Task 6: Full-suite verification

- [ ] **Step 1:** `.venv/Scripts/python.exe -m pytest tests/ -q` → ~**293 passing** (271 + ~22), zero failures. `alembic heads` → single head `d4f8b2c9e1a7`.
- [ ] **Step 2:** Route smoke-check:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'analyze' in p or 'supersede' in p))"
```
Expected:
```
/api/documents/{document_id}/supersede
/api/projects/{project_id}/documents/analyze
```
- [ ] **Step 3:** Commit anything uncommitted (skip if clean).

---

## Spec Coverage Self-Review

| Phase 7C / plan.md requirement | Task |
|---|---|
| Doc classification (configurable keywords) | 2 |
| Detect duplicates (content hash) | 3 |
| Addenda-supersedes versioning (revision chains) | 3 |
| Human override for true addenda judgment | 3, 4 (PATCH supersede) |
| Superseded docs excluded from packaging/linking (the money path) | 4 |
| Surfaced in UI (badges + analyze) | 5 |
| Idempotent / reproducible | 3 (`auto:` reset convention) |
| Migration discipline (additive, SQLite-safe, single head) | 1 |

**Documented limitations (intentional):** the v1 semantic search/extraction context still includes superseded documents (filtering retrieval is a v1-core change — out of scope; the linker exclusion protects the pricing path). Cross-document addenda semantics ("Addendum 2 replaces ITT section 5") are a human call via the manual endpoint, not auto-detected. Arabic version tokens (مراجعة) are not parsed — only Latin rev/v/issue patterns.
