# Phase 10 — Offer Evaluation + Comparison — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest supplier offers against a package, extract/score them, and compare them — adding offer CRUD + manual commercial entry, configurable rules-driven weighted scoring + ranking, an offer-comparison matrix (JSON + Excel), an AI offer-data/compliance extractor behind an injectable boundary, and bilingual clarification-email drafts that reuse the Phase 9 draft-only email pipeline.

**Architecture:** Two cleanly separated halves. (1) **Pure logic** — `OfferService` (offer CRUD + manual commercial entry + select), `ScoringService` (rules-driven weighted scoring/ranking + comparison data), comparison-matrix Excel export, and clarification drafts — all work with **no LLM key** and are fully unit-tested. (2) **Injectable AI boundary** — `OfferExtractor` mirrors `DocumentLinker`'s injectable-dependency pattern: it lazily resolves the real `GeminiService` only when not injected, raises `LLMUnavailable` (→ HTTP 503) when no key is configured, and is fake-testable. This matters because the project's Gemini key is currently disabled/leaked, so the value of the phase must not depend on it. All root conventions hold: services take `db: AsyncSession` as a param, enums are stored/compared as `.value` strings, nested responses are built from explicitly-loaded children (no lazy relationship loads → no `MissingGreenlet`), and trade/JSON filtering is done in Python (no SQLite-incompatible `.contains()`).

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + aiosqlite · openpyxl (comparison matrix — **no pandas**) · Jinja2 (clarification email body) · `instructor` + Gemini via the existing `GeminiService.extract` (sync, called through `asyncio.to_thread`) · the Phase 7 parser registry (`get_parser_for_file`) for reading offer files · pytest-asyncio + httpx ASGITransport (tests).

**No database migration is required** — the `supplier_offers` and `email_logs` tables already exist (created by migration `a2bb5607f46c`). This phase adds no columns.

---

## Pre-flight (read, do not skip)

1. **`SupplierOffer` enum fields are strings.** `status` is a `String` column holding an `OfferStatus` *value* (`app/models/supplier.py:112-114`). Always assign `OfferStatus.EVALUATED.value` and compare against `.value`. Values: `received, under_review, clarification_sent, clarification_received, compliant, non_compliant, selected, rejected`.
2. **Build nested responses from explicitly-loaded children.** Accessing `offer.supplier.name` lazily inside an async request raises `MissingGreenlet`. Load the supplier with `await db.get(Supplier, offer.supplier_id)` and pass the name in (see `app/api/packaging.py:113-139` for the established pattern).
3. **Services take `db` as a parameter** (`PackagingService().generate(db, ...)`). Do not open new sessions inside services.
4. **The LLM call is synchronous.** `GeminiService.extract(prompt=..., response_model=<PydanticModel>)` is sync; invoke it via `await asyncio.to_thread(...)` exactly as `app/services/extraction/extraction_service.py:107-111` does, and treat any exception as graceful degradation.
5. **The Gemini key is currently unusable** (leaked/disabled, free-tier). So `OfferExtractor` MUST be injectable and degrade to a clean 503 — the pure-logic scoring/comparison/manual-entry/clarification paths are the phase's testable core and must never depend on a key.
6. **Parser registry**: `from app.services.parsing.base import get_parser_for_file`; `parser = get_parser_for_file(filename)`; `parsed = await parser.parse(file_path)`; use `parsed.full_text`. `.txt/.md/.csv` are handled by the text parser (used in tests so no LLM/binary deps are needed).
7. **Checklist storage**: the requirements checklist is JSON-encoded text on `Project.checklist_json` (NOT a relationship). Parse with `json.loads`; it has top-level lists `requirements`, `submission_documents`, `eligibility_criteria`, each an array of objects with a `"requirement"` string.
8. **Rules drive scoring & currency.** Weights/thresholds come from `RulesService().load().scoring`; comparison currency falls back to `rules.commercial.currency`. `ScoringService` and `RFQService` take an injectable `rules_service` (default `RulesService()`), matching the Phase 9 pattern — tests inject a fake with a `.load()` method.
9. **Reuse the Phase 9 email pipeline for clarifications.** Clarification emails are `EmailType.CLARIFICATION.value` `EmailLog` rows created as `DRAFT` by extending `RFQService`; they are sent (if ever) through the existing `POST /api/emails/{id}/send`. `EmailLog` Python attrs are `to`/`cc`/`bcc` (NOT `to_addresses`).

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (must stay green; baseline = **106 passing**).

---

## File Structure

**Create:**
- `app/schemas/offer.py` — LLM response models (`OfferExtraction`, `ComplianceAnalysis`, `OfferLineItem`) + API request/response models.
- `app/services/offer/__init__.py`
- `app/services/offer/offer_service.py` — `OfferService` (create, get, list, manual commercial update, select).
- `app/services/offer/scoring_service.py` — `ScoringService` (rules-driven `score_package`, `compare`).
- `app/services/offer/comparison_export.py` — `build_comparison_workbook` / `export_comparison_excel` (openpyxl).
- `app/services/offer/offer_extractor.py` — `OfferExtractor` (injectable LLM; `extract_offer`, `check_compliance`) + `LLMUnavailable`.
- `app/api/offers.py` — offers router.
- `tests/offers/__init__.py`, `tests/offers/test_offer_service.py`, `tests/offers/test_scoring_service.py`, `tests/offers/test_comparison_export.py`, `tests/offers/test_offer_extractor.py`, `tests/offers/test_offers_api.py`

**Modify (extends Phase 9 email pipeline for clarifications):**
- `app/services/email/templates.py` — add `clarification` (en/ar) templates + register the type.
- `app/services/email/rfq_service.py` — add `create_clarification_drafts`.
- `app/api/emails.py` — no change needed (send is generic); clarification creation lives on the offers router.
- `app/main.py` — register `offers_router`.
- `tests/email/test_templates.py` — add a clarification render test.
- `tests/email/test_rfq_service.py` — add a clarification-draft test.

---

## Task 1: Offer schemas (API + LLM response models)

**Files:**
- Create: `app/schemas/offer.py`

- [ ] **Step 1: Write the schemas**

Create `app/schemas/offer.py`:

```python
"""Schemas for offer ingest, manual commercial entry, scoring, comparison, and
the LLM extraction/compliance response models used by OfferExtractor."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------
# LLM response models (passed to GeminiService.extract via instructor)
# ----------------------------------------------------------------------------


class OfferLineItem(BaseModel):
    description: str = ""
    unit: str | None = None
    quantity: float | None = None
    rate: float | None = None
    total: float | None = None


class OfferExtraction(BaseModel):
    """Commercial data extracted from a supplier's offer documents."""

    total_price: float | None = None
    currency: str | None = None
    vat_included: bool | None = None
    validity_days: int | None = None
    payment_terms: str | None = None
    delivery_weeks: int | None = None
    exclusions: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    line_items: list[OfferLineItem] = Field(default_factory=list)


class ComplianceAnalysis(BaseModel):
    """Compliance of an offer against the tender checklist + package scope."""

    overall_compliance: str = "UNKNOWN"  # COMPLIANT | NON_COMPLIANT | PARTIAL | UNKNOWN
    compliance_score: float = 0.0  # 0-100
    missing_items: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    clarifications_needed: list[str] = Field(default_factory=list)
    notes: str = ""


# ----------------------------------------------------------------------------
# API request/response models
# ----------------------------------------------------------------------------


class OfferCommercialUpdate(BaseModel):
    """Manual entry/edit of offer fields (works with no LLM key)."""

    total_price: float | None = None
    currency: str | None = None
    vat_included: bool | None = None
    vat_amount: float | None = None
    validity_days: int | None = None
    payment_terms: str | None = None
    delivery_weeks: int | None = None
    delivery_terms: str | None = None
    technical_score: float | None = None  # manual technical sub-score (0-100)
    exclusions: list[str] | None = None
    deviations: list[str] | None = None
    line_items: list[dict] | None = None
    evaluator_notes: str | None = None


class OfferResponse(BaseModel):
    id: int
    package_id: int
    supplier_id: int
    status: str
    total_price: float | None = None
    currency: str | None = None
    validity_days: int | None = None
    delivery_weeks: int | None = None
    payment_terms: str | None = None
    commercial_score: float | None = None
    technical_score: float | None = None
    overall_score: float | None = None
    rank: int | None = None
    file_paths: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OfferDetailResponse(OfferResponse):
    supplier_name: str | None = None
    vat_included: bool | None = None
    exclusions: list | None = None
    deviations: list | None = None
    missing_items: list | None = None
    clarifications_needed: list | None = None
    compliance_analysis: dict | None = None
    line_items: list | None = None
    evaluator_notes: str | None = None
    recommendation: str | None = None


class OfferScore(BaseModel):
    offer_id: int
    supplier_name: str
    subscores: dict[str, float]
    overall_score: float
    rank: int
    band: str


class ScorePackageResult(BaseModel):
    package_id: int
    offers_scored: int
    weights: dict[str, float]
    ranking: list[OfferScore]


class ComparisonOffer(BaseModel):
    offer_id: int
    supplier_id: int
    supplier_name: str
    total_price: float | None = None
    currency: str | None = None
    validity_days: int | None = None
    delivery_weeks: int | None = None
    payment_terms: str | None = None
    commercial_score: float | None = None
    technical_score: float | None = None
    overall_score: float | None = None
    rank: int | None = None
    status: str
    exclusions_count: int = 0
    deviations_count: int = 0


class ComparisonResponse(BaseModel):
    package_id: int
    package_name: str
    total_offers: int
    evaluated_offers: int
    currency: str
    price_min: float | None = None
    price_max: float | None = None
    price_avg: float | None = None
    offers: list[ComparisonOffer] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    items: list[str] | None = None  # defaults to offer.clarifications_needed
    language: str | None = None
    response_days: int = 3
```

- [ ] **Step 2: Verify import**

Run: `.venv/Scripts/python.exe -c "from app.schemas.offer import OfferExtraction, ComparisonResponse; print(OfferExtraction().exclusions, ComparisonResponse(package_id=1, package_name='x', total_offers=0, evaluated_offers=0, currency='USD').offers)"`
Expected: `[] []`

- [ ] **Step 3: Commit**

```bash
git add app/schemas/offer.py
git commit -m "feat(phase-10): offer schemas + LLM extraction/compliance response models"
```

---

## Task 2: OfferService — create, get, list, manual commercial update, select

**Files:**
- Create: `app/services/offer/__init__.py`, `app/services/offer/offer_service.py`
- Test: `tests/offers/__init__.py`, `tests/offers/test_offer_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/offers/__init__.py` (empty file).

Create `tests/offers/test_offer_service.py`:

```python
import pytest

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier
from app.services.offer.offer_service import OfferService


async def _seed(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                      trade_category="mep")
    db.add(package)
    supplier = Supplier(name="CoolAir", emails=["s@coolair.test"], trade_categories=["mep"])
    db.add(supplier)
    await db.commit()
    for o in (package, supplier):
        await db.refresh(o)
    return package, supplier


async def test_create_offer_increments_stats(db_session):
    package, supplier = await _seed(db_session)
    svc = OfferService()
    offer = await svc.create_offer(db_session, package.id, supplier.id, ["/tmp/a.pdf"])
    assert offer.id is not None
    assert offer.status == OfferStatus.RECEIVED.value
    assert offer.file_paths == ["/tmp/a.pdf"]
    await db_session.refresh(package)
    await db_session.refresh(supplier)
    assert package.offers_received == 1
    assert supplier.total_offers_received == 1


async def test_create_offer_unknown_package_or_supplier(db_session):
    package, supplier = await _seed(db_session)
    svc = OfferService()
    with pytest.raises(ValueError):
        await svc.create_offer(db_session, 999999, supplier.id, [])
    with pytest.raises(ValueError):
        await svc.create_offer(db_session, package.id, 999999, [])


async def test_update_commercial(db_session):
    package, supplier = await _seed(db_session)
    svc = OfferService()
    offer = await svc.create_offer(db_session, package.id, supplier.id, [])
    updated = await svc.update_commercial(
        db_session, offer.id, total_price=150000, currency="USD",
        delivery_weeks=8, technical_score=80,
    )
    assert updated.total_price == 150000
    assert updated.currency == "USD"
    assert updated.delivery_weeks == 8
    assert updated.technical_score == 80
    assert await svc.update_commercial(db_session, 999999, total_price=1) is None


async def test_list_offers(db_session):
    package, supplier = await _seed(db_session)
    svc = OfferService()
    await svc.create_offer(db_session, package.id, supplier.id, [])
    await svc.create_offer(db_session, package.id, supplier.id, [])
    offers = await svc.list_offers(db_session, package.id)
    assert len(offers) == 2


async def test_select_offer_marks_winner_and_unselects_others(db_session):
    package, supplier = await _seed(db_session)
    svc = OfferService()
    o1 = await svc.create_offer(db_session, package.id, supplier.id, [])
    o2 = await svc.create_offer(db_session, package.id, supplier.id, [])
    # select o1
    sel1 = await svc.select_offer(db_session, o1.id, notes="best price")
    assert sel1.status == OfferStatus.SELECTED.value
    assert sel1.recommendation == "best price"
    await db_session.refresh(supplier)
    assert supplier.total_awards == 1
    # selecting o2 demotes o1 back to evaluated
    await svc.select_offer(db_session, o2.id)
    await db_session.refresh(o1)
    assert o1.status == OfferStatus.EVALUATED.value
    assert await svc.select_offer(db_session, 999999) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_offer_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.offer`.

- [ ] **Step 3: Implement the service**

Create `app/services/offer/__init__.py` (empty file).

Create `app/services/offer/offer_service.py`:

```python
"""Offer lifecycle: create from files, manual commercial entry, list, select.

Pure DB/logic — no LLM. Works fully without a Gemini key.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.supplier import Supplier, SupplierOffer

_SETTABLE = (
    "total_price", "currency", "vat_included", "vat_amount", "validity_days",
    "payment_terms", "delivery_weeks", "delivery_terms", "technical_score",
    "exclusions", "deviations", "line_items", "evaluator_notes",
)


class OfferService:
    async def create_offer(
        self, db: AsyncSession, package_id: int, supplier_id: int, file_paths: list[str]
    ) -> SupplierOffer:
        package = await db.get(Package, package_id)
        if package is None:
            raise ValueError(f"Package {package_id} not found")
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            raise ValueError(f"Supplier {supplier_id} not found")
        offer = SupplierOffer(
            package_id=package_id,
            supplier_id=supplier_id,
            file_paths=list(file_paths or []),
            status=OfferStatus.RECEIVED.value,
            received_at=datetime.now(timezone.utc),
        )
        db.add(offer)
        package.offers_received = (package.offers_received or 0) + 1
        supplier.total_offers_received = (supplier.total_offers_received or 0) + 1
        await db.commit()
        await db.refresh(offer)
        return offer

    async def get_offer(self, db: AsyncSession, offer_id: int) -> SupplierOffer | None:
        return await db.get(SupplierOffer, offer_id)

    async def list_offers(self, db: AsyncSession, package_id: int) -> list[SupplierOffer]:
        stmt = (
            select(SupplierOffer)
            .where(SupplierOffer.package_id == package_id)
            .order_by(SupplierOffer.overall_score.desc().nullslast(), SupplierOffer.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def update_commercial(
        self, db: AsyncSession, offer_id: int, **fields
    ) -> SupplierOffer | None:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            return None
        for key, value in fields.items():
            if value is not None and key in _SETTABLE:
                setattr(offer, key, value)
        await db.commit()
        await db.refresh(offer)
        return offer

    async def select_offer(
        self, db: AsyncSession, offer_id: int, notes: str | None = None
    ) -> SupplierOffer | None:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            return None
        # Demote any previously-selected offer in this package back to evaluated.
        await db.execute(
            update(SupplierOffer)
            .where(
                SupplierOffer.package_id == offer.package_id,
                SupplierOffer.status == OfferStatus.SELECTED.value,
                SupplierOffer.id != offer.id,
            )
            .values(status=OfferStatus.EVALUATED.value)
        )
        offer.status = OfferStatus.SELECTED.value
        if notes is not None:
            offer.recommendation = notes
        supplier = await db.get(Supplier, offer.supplier_id)
        if supplier is not None:
            supplier.total_awards = (supplier.total_awards or 0) + 1
        await db.commit()
        await db.refresh(offer)
        return offer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_offer_service.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/offer/__init__.py app/services/offer/offer_service.py tests/offers/__init__.py tests/offers/test_offer_service.py
git commit -m "feat(phase-10): OfferService — create/list/manual-commercial/select"
```

---

## Task 3: ScoringService — rules-driven weighted scoring + ranking

**Files:**
- Create: `app/services/offer/scoring_service.py`
- Test: `tests/offers/test_scoring_service.py`

Per-dimension sub-scores (0-100): `price` (min/offer×100), `delivery_time` (min/offer×100), `technical_compliance` (manual `technical_score` → else `compliance_analysis.compliance_score` → else 50), `supplier_rating` (rating/5×100 → else 50), `payment_terms` (neutral 50 — not objectively computable; documented). `overall = Σ(weight·sub) / Σ(weight)` using `rules.scoring.weights` (normalized so a non-1.0 weight sum still yields 0-100). Persists `commercial_score`=price, `technical_score`=technical sub-score, `overall_score`, `rank`; sets status `EVALUATED` (unless already `SELECTED`/`REJECTED`).

- [ ] **Step 1: Write the failing tests**

Create `tests/offers/test_scoring_service.py`:

```python
import pytest

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.offer.scoring_service import ScoringService


async def _seed_offers(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP", trade_category="mep")
    db.add(package)
    supplier = Supplier(name="CoolAir", emails=[], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    # prices 100/150/200, delivery 4/8/6 weeks
    specs = [(100.0, 4), (150.0, 8), (200.0, 6)]
    offers = []
    for price, weeks in specs:
        o = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                          status=OfferStatus.RECEIVED.value, file_paths=[],
                          total_price=price, currency="USD", delivery_weeks=weeks)
        db.add(o)
        offers.append(o)
    await db.commit()
    for o in offers + [package]:
        await db.refresh(o)
    return package, offers


async def test_score_package_ranks_by_weighted_overall(db_session):
    package, offers = await _seed_offers(db_session)
    result = await ScoringService().score_package(db_session, package.id)
    assert result["offers_scored"] == 3
    ranking = result["ranking"]
    # cheapest + fastest wins
    assert ranking[0]["rank"] == 1
    top = ranking[0]
    # default weights: price .35, delivery .15, technical .30, payment .10, rating .10
    # offer A: price=100, delivery=100, technical=50, payment=50, rating=50 -> 75.0
    assert top["subscores"]["price"] == 100.0
    assert top["subscores"]["delivery_time"] == 100.0
    assert top["overall_score"] == 75.0
    assert top["band"] in ("good", "acceptable", "excellent", "poor", "unacceptable")
    # overall strictly descending
    overalls = [r["overall_score"] for r in ranking]
    assert overalls == sorted(overalls, reverse=True)


async def test_score_persists_fields_and_status(db_session):
    package, offers = await _seed_offers(db_session)
    await ScoringService().score_package(db_session, package.id)
    for o in offers:
        await db_session.refresh(o)
        assert o.overall_score is not None
        assert o.rank in (1, 2, 3)
        assert o.commercial_score is not None
        assert o.status == OfferStatus.EVALUATED.value


async def test_technical_score_override_used(db_session):
    package, offers = await _seed_offers(db_session)
    offers[2].technical_score = 100.0  # most expensive but perfect technical
    await db_session.commit()
    result = await ScoringService().score_package(db_session, package.id)
    by_id = {r["offer_id"]: r for r in result["ranking"]}
    assert by_id[offers[2].id]["subscores"]["technical_compliance"] == 100.0


async def test_score_handles_missing_prices_neutral(db_session):
    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    package = Package(project_id=project.id, name="X", code="C", trade_category="mep")
    db_session.add(package)
    supplier = Supplier(name="S", emails=[], trade_categories=["mep"])
    db_session.add(supplier)
    await db_session.flush()
    o = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.RECEIVED.value, file_paths=[])
    db_session.add(o)
    await db_session.commit()
    result = await ScoringService().score_package(db_session, package.id)
    sub = result["ranking"][0]["subscores"]
    assert sub["price"] == 50.0  # neutral when nobody has a price
    assert sub["delivery_time"] == 50.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_scoring_service.py -q`
Expected: FAIL — `ModuleNotFoundError: ...scoring_service`.

- [ ] **Step 3: Implement the service**

Create `app/services/offer/scoring_service.py`:

```python
"""Configurable weighted scoring + ranking + comparison for package offers.

Sub-scores per offer (0-100): price, delivery_time, technical_compliance,
supplier_rating, payment_terms. overall = sum(weight*sub)/sum(weight) using
rules.scoring.weights. Pure logic — no LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.supplier import Supplier, SupplierOffer
from app.services.rules.rules_service import RulesService

_NEUTRAL = 50.0
_TERMINAL = (OfferStatus.SELECTED.value, OfferStatus.REJECTED.value)


class ScoringService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    def _rules(self):
        return self._rules_service.load()

    @staticmethod
    def _ratio_score(value: float | None, best: float | None) -> float:
        """100 when value == best (the minimum); lower as value grows."""
        if best is None:
            return _NEUTRAL
        if not value or value <= 0:
            return 0.0
        return round(min(100.0, 100.0 * best / value), 1)

    @staticmethod
    def _band(score: float, thresholds) -> str:
        if score >= thresholds.excellent:
            return "excellent"
        if score >= thresholds.good:
            return "good"
        if score >= thresholds.acceptable:
            return "acceptable"
        if score >= thresholds.poor:
            return "poor"
        return "unacceptable"

    async def _offers(self, db: AsyncSession, package_id: int) -> list[SupplierOffer]:
        return list(
            (
                await db.execute(
                    select(SupplierOffer)
                    .where(SupplierOffer.package_id == package_id)
                    .order_by(SupplierOffer.id)
                )
            ).scalars().all()
        )

    async def score_package(self, db: AsyncSession, package_id: int) -> dict:
        offers = await self._offers(db, package_id)
        scoring = self._rules().scoring
        weights = scoring.weights.model_dump()
        wsum = sum(weights.values()) or 1.0

        prices = [o.total_price for o in offers if o.total_price and o.total_price > 0]
        min_price = min(prices) if prices else None
        deliveries = [o.delivery_weeks for o in offers if o.delivery_weeks and o.delivery_weeks > 0]
        min_delivery = min(deliveries) if deliveries else None

        scored: list[tuple] = []
        for offer in offers:
            supplier = await db.get(Supplier, offer.supplier_id)
            technical = offer.technical_score
            if technical is None and offer.compliance_analysis:
                technical = offer.compliance_analysis.get("compliance_score")
            sub = {
                "price": self._ratio_score(offer.total_price, min_price),
                "delivery_time": self._ratio_score(offer.delivery_weeks, min_delivery),
                "technical_compliance": float(technical) if technical is not None else _NEUTRAL,
                "supplier_rating": (
                    round(supplier.rating / 5.0 * 100.0, 1)
                    if supplier and supplier.rating
                    else _NEUTRAL
                ),
                "payment_terms": _NEUTRAL,
            }
            overall = round(
                sum(weights.get(k, 0.0) * sub.get(k, 0.0) for k in weights) / wsum, 1
            )
            offer.commercial_score = sub["price"]
            offer.technical_score = sub["technical_compliance"]
            offer.overall_score = overall
            offer.evaluated_at = datetime.now(timezone.utc)
            if offer.status not in _TERMINAL:
                offer.status = OfferStatus.EVALUATED.value
            scored.append((offer, sub, overall, supplier.name if supplier else ""))

        scored.sort(key=lambda r: r[2], reverse=True)
        ranking = []
        for rank, (offer, sub, overall, supplier_name) in enumerate(scored, 1):
            offer.rank = rank
            ranking.append(
                {
                    "offer_id": offer.id,
                    "supplier_name": supplier_name,
                    "subscores": sub,
                    "overall_score": overall,
                    "rank": rank,
                    "band": self._band(overall, scoring.thresholds),
                }
            )
        await db.commit()
        return {
            "package_id": package_id,
            "offers_scored": len(offers),
            "weights": weights,
            "ranking": ranking,
        }

    async def compare(self, db: AsyncSession, package_id: int) -> dict:
        package = await db.get(Package, package_id)
        if package is None:
            raise ValueError(f"Package {package_id} not found")
        offers = list(
            (
                await db.execute(
                    select(SupplierOffer)
                    .where(SupplierOffer.package_id == package_id)
                    .order_by(SupplierOffer.overall_score.desc().nullslast(), SupplierOffer.id)
                )
            ).scalars().all()
        )
        rows = []
        prices = []
        for offer in offers:
            supplier = await db.get(Supplier, offer.supplier_id)
            if offer.total_price:
                prices.append(offer.total_price)
            rows.append(
                {
                    "offer_id": offer.id,
                    "supplier_id": offer.supplier_id,
                    "supplier_name": supplier.name if supplier else "",
                    "total_price": offer.total_price,
                    "currency": offer.currency,
                    "validity_days": offer.validity_days,
                    "delivery_weeks": offer.delivery_weeks,
                    "payment_terms": offer.payment_terms,
                    "commercial_score": offer.commercial_score,
                    "technical_score": offer.technical_score,
                    "overall_score": offer.overall_score,
                    "rank": offer.rank,
                    "status": offer.status,
                    "exclusions_count": len(offer.exclusions or []),
                    "deviations_count": len(offer.deviations or []),
                }
            )
        currency = next((o.currency for o in offers if o.currency), self._rules().commercial.currency)
        return {
            "package_id": package_id,
            "package_name": package.name,
            "total_offers": len(offers),
            "evaluated_offers": len([o for o in offers if o.overall_score is not None]),
            "currency": currency,
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "price_avg": round(sum(prices) / len(prices), 2) if prices else None,
            "offers": rows,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_scoring_service.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/offer/scoring_service.py tests/offers/test_scoring_service.py
git commit -m "feat(phase-10): ScoringService — rules-driven weighted scoring, ranking, comparison data"
```

---

## Task 4: Comparison-matrix Excel export

**Files:**
- Create: `app/services/offer/comparison_export.py`
- Test: `tests/offers/test_comparison_export.py`

Pure function over the `compare()` dict (no DB) — easy to test. Highlights rank 1.

- [ ] **Step 1: Write the failing test**

Create `tests/offers/test_comparison_export.py`:

```python
import openpyxl

from app.services.offer.comparison_export import export_comparison_excel

COMPARISON = {
    "package_id": 1,
    "package_name": "HVAC Works",
    "total_offers": 2,
    "evaluated_offers": 2,
    "currency": "USD",
    "price_min": 100.0,
    "price_max": 150.0,
    "price_avg": 125.0,
    "offers": [
        {"offer_id": 1, "supplier_id": 1, "supplier_name": "CoolAir", "total_price": 100.0,
         "currency": "USD", "validity_days": 90, "delivery_weeks": 4, "payment_terms": "Net 30",
         "commercial_score": 100.0, "technical_score": 50.0, "overall_score": 75.0, "rank": 1,
         "status": "evaluated", "exclusions_count": 0, "deviations_count": 1},
        {"offer_id": 2, "supplier_id": 2, "supplier_name": "HawaCo", "total_price": 150.0,
         "currency": "USD", "validity_days": 60, "delivery_weeks": 8, "payment_terms": "Net 60",
         "commercial_score": 66.7, "technical_score": 50.0, "overall_score": 55.8, "rank": 2,
         "status": "evaluated", "exclusions_count": 1, "deviations_count": 0},
    ],
}


def test_export_writes_matrix(tmp_path):
    out = export_comparison_excel(COMPARISON, str(tmp_path / "cmp.xlsx"))
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert ws.title == "Offer Comparison"
    # header row contains the key columns
    header = [c.value for c in ws[5]]
    assert "Rank" in header and "Supplier" in header and "Overall Score" in header
    # first data row is the rank-1 supplier
    row6 = [c.value for c in ws[6]]
    assert "CoolAir" in row6
    assert 75.0 in row6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_comparison_export.py -q`
Expected: FAIL — `ModuleNotFoundError: ...comparison_export`.

- [ ] **Step 3: Implement the export**

Create `app/services/offer/comparison_export.py`:

```python
"""Render an offer-comparison matrix to an .xlsx workbook (openpyxl)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_HEADERS = [
    "Rank", "Supplier", "Total Price", "Currency", "Validity (days)",
    "Delivery (weeks)", "Payment Terms", "Commercial Score", "Technical Score",
    "Overall Score", "Status", "Exclusions", "Deviations",
]
_WIDTHS = [6, 28, 14, 9, 14, 16, 18, 16, 16, 14, 14, 11, 11]


def build_comparison_workbook(comparison: dict) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Offer Comparison"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    best_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    border = Border(left=Side(style="thin"), right=Side(style="thin"),
                    top=Side(style="thin"), bottom=Side(style="thin"))

    last_col = get_column_letter(len(_HEADERS))
    ws.merge_cells(f"A1:{last_col}1")
    ws["A1"] = f"Offer Comparison - {comparison.get('package_name', '')}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws["A3"] = "Total Offers:"
    ws["B3"] = comparison.get("total_offers", 0)
    ws["C3"] = "Lowest Price:"
    ws["D3"] = comparison.get("price_min")
    ws["E3"] = comparison.get("currency", "")

    for col, header in enumerate(_HEADERS, 1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center")

    for row_idx, offer in enumerate(comparison.get("offers", []), 6):
        values = [
            offer.get("rank") or "-",
            offer.get("supplier_name") or "",
            offer.get("total_price") if offer.get("total_price") is not None else "-",
            offer.get("currency") or "",
            offer.get("validity_days") if offer.get("validity_days") is not None else "-",
            offer.get("delivery_weeks") if offer.get("delivery_weeks") is not None else "-",
            offer.get("payment_terms") or "-",
            round(offer.get("commercial_score") or 0, 1),
            round(offer.get("technical_score") or 0, 1),
            round(offer.get("overall_score") or 0, 1),
            offer.get("status") or "",
            offer.get("exclusions_count", 0),
            offer.get("deviations_count", 0),
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.border = border
            if offer.get("rank") == 1:
                cell.fill = best_fill

    for col, width in enumerate(_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    return wb


def export_comparison_excel(comparison: dict, output_path: str) -> str:
    wb = build_comparison_workbook(comparison)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_comparison_export.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add app/services/offer/comparison_export.py tests/offers/test_comparison_export.py
git commit -m "feat(phase-10): offer comparison-matrix Excel export"
```

---

## Task 5: OfferExtractor — injectable AI extraction + compliance

**Files:**
- Create: `app/services/offer/offer_extractor.py`
- Test: `tests/offers/test_offer_extractor.py`

Mirrors `DocumentLinker`'s injectable dependency. The real `GeminiService` is resolved lazily from settings keys; if none are configured, `_resolve_llm()` returns `None` and the public methods raise `LLMUnavailable` (the API maps that to 503). Tests inject a fake LLM whose `extract(prompt, response_model)` returns a populated `OfferExtraction`/`ComplianceAnalysis`.

- [ ] **Step 1: Write the failing tests**

Create `tests/offers/test_offer_extractor.py`:

```python
import json

import pytest

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.schemas.offer import ComplianceAnalysis, OfferExtraction
from app.services.offer.offer_extractor import LLMUnavailable, OfferExtractor


class _FakeLLM:
    def __init__(self, result):
        self._result = result
        self.prompts = []

    def extract(self, prompt, response_model):
        self.prompts.append(prompt)
        return self._result


async def _seed_offer(db, tmp_path, *, checklist=None):
    project = Project(name="Metro")
    if checklist is not None:
        project.checklist_json = json.dumps(checklist)
    db.add(project)
    await db.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP", trade_category="mep")
    db.add(package)
    await db.flush()
    db.add(BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                   description="Supply chillers", unit="no", quantity=2,
                   client_row_index=1, trade_category="mep"))
    supplier = Supplier(name="CoolAir", emails=["s@coolair.test"], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    offer_file = tmp_path / "offer.txt"
    offer_file.write_text("Our price is 150000 USD, validity 90 days, delivery 8 weeks.")
    offer = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                          status=OfferStatus.RECEIVED.value, file_paths=[str(offer_file)])
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


async def test_extract_offer_populates_fields(db_session, tmp_path):
    offer = await _seed_offer(db_session, tmp_path)
    fake = OfferExtraction(total_price=150000, currency="USD", validity_days=90,
                           delivery_weeks=8, exclusions=["site cleanup"])
    ex = OfferExtractor(llm_service=_FakeLLM(fake))
    out = await ex.extract_offer(db_session, offer.id)
    assert out["total_price"] == 150000
    await db_session.refresh(offer)
    assert offer.total_price == 150000
    assert offer.currency == "USD"
    assert offer.delivery_weeks == 8
    assert offer.exclusions == ["site cleanup"]
    assert offer.status == OfferStatus.UNDER_REVIEW.value


async def test_check_compliance_sets_status_and_fields(db_session, tmp_path):
    checklist = {"requirements": [{"requirement": "ISO 9001 certificate"}],
                 "submission_documents": [], "eligibility_criteria": []}
    offer = await _seed_offer(db_session, tmp_path, checklist=checklist)
    fake = ComplianceAnalysis(overall_compliance="NON_COMPLIANT", compliance_score=40,
                              missing_items=["ISO 9001 certificate"],
                              clarifications_needed=["Provide ISO 9001 cert"])
    ex = OfferExtractor(llm_service=_FakeLLM(fake))
    out = await ex.check_compliance(db_session, offer.id)
    assert out["overall_compliance"] == "NON_COMPLIANT"
    await db_session.refresh(offer)
    assert offer.status == OfferStatus.NON_COMPLIANT.value
    assert offer.clarifications_needed == ["Provide ISO 9001 cert"]
    assert offer.compliance_analysis["compliance_score"] == 40


async def test_compliance_compliant_status(db_session, tmp_path):
    offer = await _seed_offer(db_session, tmp_path, checklist={"requirements": [], "submission_documents": [], "eligibility_criteria": []})
    fake = ComplianceAnalysis(overall_compliance="COMPLIANT", compliance_score=95)
    ex = OfferExtractor(llm_service=_FakeLLM(fake))
    await ex.check_compliance(db_session, offer.id)
    await db_session.refresh(offer)
    assert offer.status == OfferStatus.COMPLIANT.value


async def test_extract_raises_when_llm_unavailable(db_session, tmp_path, monkeypatch):
    offer = await _seed_offer(db_session, tmp_path)
    ex = OfferExtractor()
    monkeypatch.setattr(ex, "_resolve_llm", lambda: None)
    with pytest.raises(LLMUnavailable):
        await ex.extract_offer(db_session, offer.id)


async def test_extract_unknown_offer_raises(db_session):
    ex = OfferExtractor(llm_service=_FakeLLM(OfferExtraction()))
    with pytest.raises(ValueError):
        await ex.extract_offer(db_session, 999999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_offer_extractor.py -q`
Expected: FAIL — `ModuleNotFoundError: ...offer_extractor`.

- [ ] **Step 3: Implement the extractor**

Create `app/services/offer/offer_extractor.py`:

```python
"""AI offer-data extraction + compliance analysis behind an injectable boundary.

The real GeminiService is resolved lazily from configured keys; when no key is
available _resolve_llm() returns None and the public methods raise
LLMUnavailable (the API maps that to 503). The LLM dependency is injectable so
the parse+map logic is testable without a key (mirrors DocumentLinker).
"""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import SupplierOffer
from app.schemas.offer import ComplianceAnalysis, OfferExtraction
from app.services.parsing.base import get_parser_for_file

logger = logging.getLogger(__name__)

_MAX_FILE_CHARS = 10000
_MAX_TOTAL_CHARS = 30000

_EXTRACTION_PROMPT = """You are extracting commercial data from a supplier's offer for package "{package_name}".

Required BOQ items (for context):
{items}

Offer documents:
{content}

Extract the total price, currency, VAT inclusion, validity (days), payment terms,
delivery time (weeks), any exclusions, any deviations, and priced line items.
"""

_COMPLIANCE_PROMPT = """Assess this supplier offer against the tender requirements for package "{package_name}".

Requirements:
{requirements}

Offer summary:
{offer}

Decide overall_compliance (COMPLIANT / NON_COMPLIANT / PARTIAL), a 0-100
compliance_score, any missing_items, deviations, and clarifications_needed.
"""


class LLMUnavailable(RuntimeError):
    """Raised when no Gemini key is configured for AI extraction/compliance."""


class OfferExtractor:
    def __init__(self, llm_service=None) -> None:
        self._injected = llm_service

    def _resolve_llm(self):
        if self._injected is not None:
            return self._injected
        from app.config import get_settings
        from app.services.llm.gemini_service import GeminiService

        settings = get_settings()
        keys = settings.gemini_key_list()
        if not keys:
            return None
        return GeminiService(api_keys=keys, model=settings.gemini_model)

    async def _offer_text(self, offer: SupplierOffer) -> str:
        chunks: list[str] = []
        for file_path in offer.file_paths or []:
            try:
                parser = get_parser_for_file(file_path)
                parsed = await parser.parse(file_path)
                chunks.append((parsed.full_text or "")[:_MAX_FILE_CHARS])
            except Exception as exc:  # noqa: BLE001 - a bad file should not abort extraction
                logger.warning("Failed to parse offer file %s: %s", file_path, exc)
        return "\n\n---\n\n".join(chunks)[:_MAX_TOTAL_CHARS]

    async def extract_offer(self, db: AsyncSession, offer_id: int) -> dict:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        llm = self._resolve_llm()
        if llm is None:
            raise LLMUnavailable("No Gemini API key configured for offer extraction")

        package = await db.get(Package, offer.package_id)
        items = (
            await db.execute(
                select(BOQItem.line_number, BOQItem.description, BOQItem.unit)
                .where(BOQItem.package_id == offer.package_id)
                .order_by(BOQItem.client_row_index)
                .limit(20)
            )
        ).all()
        items_text = "\n".join(
            f"- {ln}: {(desc or '')[:100]} ({unit or ''})" for ln, desc, unit in items
        )
        prompt = _EXTRACTION_PROMPT.format(
            package_name=package.name if package else "",
            items=items_text,
            content=await self._offer_text(offer),
        )
        result: OfferExtraction = await asyncio.to_thread(
            llm.extract, prompt=prompt, response_model=OfferExtraction
        )

        offer.total_price = result.total_price
        offer.currency = result.currency
        offer.vat_included = result.vat_included
        offer.validity_days = result.validity_days
        offer.payment_terms = result.payment_terms
        offer.delivery_weeks = result.delivery_weeks
        offer.exclusions = result.exclusions
        offer.deviations = result.deviations
        offer.line_items = [li.model_dump() for li in result.line_items]
        offer.status = OfferStatus.UNDER_REVIEW.value
        await db.commit()
        return result.model_dump()

    async def check_compliance(self, db: AsyncSession, offer_id: int) -> dict:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        llm = self._resolve_llm()
        if llm is None:
            raise LLMUnavailable("No Gemini API key configured for compliance check")

        package = await db.get(Package, offer.package_id)
        project = await db.get(Project, package.project_id) if package else None
        requirements = self._checklist_requirements(project)
        boq_items = (
            await db.execute(
                select(BOQItem.description)
                .where(BOQItem.package_id == offer.package_id)
                .order_by(BOQItem.client_row_index)
                .limit(30)
            )
        ).scalars().all()
        requirements += [f"- BOQ Item: {(d or '')[:100]}" for d in boq_items]
        offer_summary = (
            f"Total Price: {offer.total_price} {offer.currency or ''}\n"
            f"Payment Terms: {offer.payment_terms or 'n/a'}\n"
            f"Delivery: {offer.delivery_weeks or 'n/a'} weeks\n"
            f"Validity: {offer.validity_days or 'n/a'} days\n"
            f"Exclusions: {offer.exclusions or []}\n"
            f"Line items provided: {len(offer.line_items or [])}"
        )
        prompt = _COMPLIANCE_PROMPT.format(
            package_name=package.name if package else "",
            requirements="\n".join(requirements[:50]) or "(none provided)",
            offer=offer_summary,
        )
        result: ComplianceAnalysis = await asyncio.to_thread(
            llm.extract, prompt=prompt, response_model=ComplianceAnalysis
        )

        offer.compliance_analysis = result.model_dump()
        offer.missing_items = result.missing_items
        offer.deviations = result.deviations or offer.deviations
        offer.clarifications_needed = result.clarifications_needed
        verdict = (result.overall_compliance or "").upper()
        if verdict == "COMPLIANT":
            offer.status = OfferStatus.COMPLIANT.value
        elif verdict == "NON_COMPLIANT":
            offer.status = OfferStatus.NON_COMPLIANT.value
        else:
            offer.status = OfferStatus.UNDER_REVIEW.value
        await db.commit()
        return result.model_dump()

    @staticmethod
    def _checklist_requirements(project: Project | None) -> list[str]:
        if project is None or not project.checklist_json:
            return []
        try:
            data = json.loads(project.checklist_json)
        except (ValueError, TypeError):
            return []
        out: list[str] = []
        for key in ("requirements", "submission_documents", "eligibility_criteria"):
            for req in data.get(key, []) or []:
                text = req.get("requirement") if isinstance(req, dict) else None
                if text:
                    out.append(f"- {text}")
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_offer_extractor.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/offer/offer_extractor.py tests/offers/test_offer_extractor.py
git commit -m "feat(phase-10): injectable OfferExtractor — AI offer extraction + compliance, graceful 503"
```

---

## Task 6: Clarification email drafts (extends Phase 9 pipeline)

**Files:**
- Modify: `app/services/email/templates.py`, `app/services/email/rfq_service.py`
- Test: `tests/email/test_templates.py`, `tests/email/test_rfq_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/email/test_templates.py`:

```python
def test_render_clarification_lists_items():
    html = render_body("clarification", "en", {
        "contact_name": "Sara", "project_name": "Metro", "package_name": "HVAC",
        "clarification_items": ["Confirm delivery date", "Provide ISO cert"],
        "response_deadline": "2026-07-01", "sender_name": "BidOps AI", "company_name": "BidOps",
    })
    assert "Confirm delivery date" in html and "Provide ISO cert" in html
    assert "2026-07-01" in html


def test_render_clarification_ar_is_rtl():
    html = render_body("clarification", "ar", {
        "contact_name": "Sara", "project_name": "Metro", "package_name": "HVAC",
        "clarification_items": ["بند"], "response_deadline": "2026-07-01",
        "sender_name": "BidOps", "company_name": "BidOps",
    })
    assert 'dir="rtl"' in html
```

Add to `tests/email/test_rfq_service.py` (the `_seed` helper there already creates a project, package `PKG-001-MEP`, and `sup_en`/`sup_ar`/`sup_none`):

```python
async def test_create_clarification_draft(db_session):
    from app.models.base import EmailStatus, EmailType
    from app.models.supplier import SupplierOffer

    _, package, sup_en, *_ = await _seed(db_session)
    offer = SupplierOffer(package_id=package.id, supplier_id=sup_en.id,
                          status="received", file_paths=[],
                          clarifications_needed=["Confirm lead time"])
    db_session.add(offer)
    await db_session.commit()
    await db_session.refresh(offer)

    draft = await RFQService().create_clarification_drafts(db_session, offer.id)
    assert draft.email_type == EmailType.CLARIFICATION.value
    assert draft.status == EmailStatus.DRAFT.value
    assert draft.offer_id == offer.id
    assert draft.to == ["sales@coolair.test"]
    assert "Confirm lead time" in draft.body_html


async def test_clarification_uses_explicit_items_and_subject(db_session):
    from app.models.supplier import SupplierOffer

    _, package, sup_en, *_ = await _seed(db_session)
    offer = SupplierOffer(package_id=package.id, supplier_id=sup_en.id, status="received", file_paths=[])
    db_session.add(offer)
    await db_session.commit()
    await db_session.refresh(offer)

    draft = await RFQService().create_clarification_drafts(
        db_session, offer.id, items=["Clarify scope of HVAC"]
    )
    assert "Clarify scope of HVAC" in draft.body_html
    # default rules subject: "[{project_code}] Clarification Request - {supplier_name}"
    assert draft.subject == "[Metro Line 3] Clarification Request - CoolAir"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_templates.py tests/email/test_rfq_service.py -q`
Expected: FAIL — `No template for email_type='clarification'` and `RFQService` has no `create_clarification_drafts`.

- [ ] **Step 3: Add the clarification templates**

In `app/services/email/templates.py`, add two template strings before the `_TEMPLATES` dict:

```python
_CLARIFICATION_EN = """\
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Dear {{ contact_name }},</p>
<p>Thank you for your offer for <strong>{{ package_name }}</strong> ({{ project_name }}).
After reviewing it we require clarification on the following points:</p>
<ol>
{% for item in clarification_items %}<li>{{ item }}</li>
{% else %}<li>(no items specified)</li>
{% endfor %}</ol>
<p>Please respond by <strong>{{ response_deadline }}</strong>.</p>
<p>Best regards,<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""

_CLARIFICATION_AR = """\
<html><body dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>السادة {{ contact_name }},</p>
<p>شكرًا لعرضكم الخاص بـ <strong>{{ package_name }}</strong> ({{ project_name }}).
بعد مراجعته نحتاج إلى توضيح النقاط التالية:</p>
<ol>
{% for item in clarification_items %}<li>{{ item }}</li>
{% else %}<li>(لا توجد بنود)</li>
{% endfor %}</ol>
<p>يرجى الرد بحلول <strong>{{ response_deadline }}</strong>.</p>
<p>مع خالص التحية،<br>{{ sender_name }}<br>{{ company_name }}</p>
</body></html>
"""
```

Then register them in the `_TEMPLATES` dict and the `SUPPORTED_TYPES` tuple:

```python
_TEMPLATES = {
    ("rfq", "en"): _RFQ_EN,
    ("rfq", "ar"): _RFQ_AR,
    ("reminder", "en"): _REMINDER_EN,
    ("reminder", "ar"): _REMINDER_AR,
    ("clarification", "en"): _CLARIFICATION_EN,
    ("clarification", "ar"): _CLARIFICATION_AR,
}

SUPPORTED_TYPES = ("rfq", "reminder", "clarification")
```

And extend the default-context dict inside `render_body` so the clarification loop variable is always present. Change the existing line:

```python
    ctx = {"attachments": [], "custom_message": None, "time_remaining": "", **context}
```

to:

```python
    ctx = {
        "attachments": [],
        "custom_message": None,
        "time_remaining": "",
        "clarification_items": [],
        "response_deadline": "",
        **context,
    }
```

- [ ] **Step 4: Add `create_clarification_drafts` to `RFQService`**

In `app/services/email/rfq_service.py`, add this method to the `RFQService` class (after `create_rfq_drafts`). It reuses the same helpers (`_from_address`, `_safe_format`, `get_settings_name`, `company_name`, `render_body`, `html_to_text`) already in that module:

```python
    async def create_clarification_drafts(
        self,
        db: AsyncSession,
        offer_id: int,
        *,
        items: list[str] | None = None,
        language: str | None = None,
        response_days: int = 3,
    ) -> EmailLog:
        """Create a DRAFT clarification email for an offer's supplier.

        Draft-only: never sends. Items default to the offer's
        clarifications_needed. Send later via POST /api/emails/{id}/send.
        """
        from datetime import timedelta

        from app.models.supplier import Supplier, SupplierOffer

        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        supplier = await db.get(Supplier, offer.supplier_id)
        if supplier is None or not supplier.emails:
            raise ValueError("Supplier has no email address")
        package = await db.get(Package, offer.package_id)
        project = await db.get(Project, package.project_id) if package else None

        rules = self._rules()
        clar_items = items if items is not None else (offer.clarifications_needed or [])
        lang = language or supplier.preferred_language or rules.email.default_language or "en"
        response_deadline = (
            datetime.now(timezone.utc) + timedelta(days=response_days)
        ).strftime("%Y-%m-%d")
        project_name = project.name if project else "Project"

        context = {
            "contact_name": supplier.contact_name or supplier.name,
            "project_name": project_name,
            "package_name": package.name if package else "",
            "clarification_items": list(clar_items),
            "response_deadline": response_deadline,
            "sender_name": get_settings_name(),
            "company_name": company_name(),
        }
        body_html = render_body("clarification", lang, context)
        subject = _safe_format(
            rules.email.subject_formats.clarification,
            project_code=project_name,
            package_name=package.name if package else "",
            package_code=package.code if package else "",
            supplier_name=supplier.name,
        )
        email_log = EmailLog(
            package_id=offer.package_id,
            supplier_id=supplier.id,
            offer_id=offer.id,
            email_type=EmailType.CLARIFICATION.value,
            status=EmailStatus.DRAFT.value,
            to=list(supplier.emails),
            subject=subject,
            body_html=body_html,
            body_text=html_to_text(body_html),
            from_address=self._from_address(rules) or None,
            reply_to=rules.email.reply_to or None,
        )
        db.add(email_log)
        await db.commit()
        await db.refresh(email_log)
        return email_log
```

> The module already imports `EmailLog`, `EmailType`, `EmailStatus`, `Package`, `Project`, `datetime`, `timezone` at the top (from Phase 9). Verify those imports exist; `Supplier`/`SupplierOffer`/`timedelta` are imported locally in the method above. If `Package`/`Project` are not already top-level imports in the file, add them.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/email/test_templates.py tests/email/test_rfq_service.py -q`
Expected: PASS (all, including the 2 new template tests + 2 new clarification tests).

- [ ] **Step 6: Commit**

```bash
git add app/services/email/templates.py app/services/email/rfq_service.py tests/email/test_templates.py tests/email/test_rfq_service.py
git commit -m "feat(phase-10): bilingual clarification email drafts (reuses Phase 9 pipeline)"
```

---

## Task 7: Offers API router

**Files:**
- Create: `app/api/offers.py`
- Modify: `app/main.py`
- Test: `tests/offers/test_offers_api.py`

Endpoints:
- `POST  /api/projects/{pid}/packages/{pkg}/offers` — multipart upload (`supplier_id` form + 1+ `files`); saves under `data/offers/pkg_{pkg}/sup_{sid}/` and creates the offer.
- `GET   /api/projects/{pid}/packages/{pkg}/offers` — list offers.
- `POST  /api/projects/{pid}/packages/{pkg}/offers/score` — score + rank (`ScorePackageResult`).
- `GET   /api/projects/{pid}/packages/{pkg}/offers/comparison` — comparison data (`ComparisonResponse`).
- `GET   /api/projects/{pid}/packages/{pkg}/offers/comparison.xlsx` — download the matrix.
- `GET   /api/offers/{offer_id}` — detail (`OfferDetailResponse`).
- `PATCH /api/offers/{offer_id}` — manual commercial update.
- `POST  /api/offers/{offer_id}/extract` — AI extract (503 if no LLM).
- `POST  /api/offers/{offer_id}/check-compliance` — AI compliance (503 if no LLM).
- `POST  /api/offers/{offer_id}/select` — select winner.
- `POST  /api/offers/{offer_id}/clarification` — create clarification draft (`EmailLogResponse`).

- [ ] **Step 1: Write the failing tests**

Create `tests/offers/test_offers_api.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def offers_client(tmp_path, monkeypatch):
    # Save uploaded offer files under tmp, not the repo's data/ dir.
    monkeypatch.chdir(tmp_path)
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
        package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP", trade_category="mep")
        seed.add(package)
        seed.add(Supplier(name="CoolAir", emails=["s@coolair.test"], trade_categories=["mep"]))
        await seed.commit()
        sup = (await seed.execute(select(Supplier))).scalars().first()
        ids = {"project": project.id, "package": package.id, "supplier": sup.id}

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, ids
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_ingest_list_patch_detail(offers_client):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    async with client as c:
        up = await c.post(
            base,
            data={"supplier_id": str(ids["supplier"])},
            files={"files": ("offer.txt", b"price 100000 usd", "text/plain")},
        )
        assert up.status_code == 201, up.text
        offer_id = up.json()["id"]
        assert up.json()["status"] == "received"

        lst = await c.get(base)
        assert lst.status_code == 200 and len(lst.json()) == 1

        patched = await c.patch(f"/api/offers/{offer_id}",
                                json={"total_price": 100000, "currency": "USD", "delivery_weeks": 6})
        assert patched.status_code == 200
        assert patched.json()["total_price"] == 100000

        detail = await c.get(f"/api/offers/{offer_id}")
        assert detail.status_code == 200
        assert detail.json()["supplier_name"] == "CoolAir"
        assert (await c.get("/api/offers/999999")).status_code == 404


async def test_score_compare_and_xlsx(offers_client):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    async with client as c:
        # two offers via ingest + manual price
        for price, weeks in ((100000, 4), (150000, 8)):
            up = await c.post(base, data={"supplier_id": str(ids["supplier"])},
                              files={"files": ("o.txt", b"x", "text/plain")})
            oid = up.json()["id"]
            await c.patch(f"/api/offers/{oid}", json={"total_price": price, "delivery_weeks": weeks})

        score = await c.post(f"{base}/score")
        assert score.status_code == 200, score.text
        assert score.json()["offers_scored"] == 2
        assert score.json()["ranking"][0]["rank"] == 1

        cmp = await c.get(f"{base}/comparison")
        assert cmp.status_code == 200
        assert cmp.json()["total_offers"] == 2
        assert cmp.json()["price_min"] == 100000

        xlsx = await c.get(f"{base}/comparison.xlsx")
        assert xlsx.status_code == 200
        assert xlsx.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert len(xlsx.content) > 0


async def test_select_and_clarification(offers_client):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    async with client as c:
        up = await c.post(base, data={"supplier_id": str(ids["supplier"])},
                          files={"files": ("o.txt", b"x", "text/plain")})
        oid = up.json()["id"]
        sel = await c.post(f"/api/offers/{oid}/select", json={"notes": "winner"})
        assert sel.status_code == 200 and sel.json()["status"] == "selected"

        clar = await c.post(f"/api/offers/{oid}/clarification",
                            json={"items": ["Confirm delivery"]})
        assert clar.status_code == 201, clar.text
        assert clar.json()["email_type"] == "clarification"
        assert clar.json()["status"] == "draft"
        assert "Confirm delivery" in clar.json()["body_html"]


async def test_extract_returns_503_without_llm(offers_client, monkeypatch):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    import app.api.offers as offers_api
    from app.services.offer.offer_extractor import LLMUnavailable

    class _NoLLM:
        async def extract_offer(self, db, offer_id):
            raise LLMUnavailable("no key")

    # monkeypatch auto-restores the real class after the test (no leakage).
    monkeypatch.setattr(offers_api, "OfferExtractor", lambda: _NoLLM())
    async with client as c:
        up = await c.post(base, data={"supplier_id": str(ids["supplier"])},
                          files={"files": ("o.txt", b"x", "text/plain")})
        oid = up.json()["id"]
        r = await c.post(f"/api/offers/{oid}/extract")
        assert r.status_code == 503


async def test_score_404_missing_package(offers_client):
    client, ids = offers_client
    async with client as c:
        r = await c.post(f"/api/projects/{ids['project']}/packages/999999/offers/score")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_offers_api.py -q`
Expected: FAIL — router not registered / 404s.

- [ ] **Step 3: Implement the router**

Create `app/api/offers.py`:

```python
"""Offers API: ingest, manual entry, AI extraction/compliance, scoring,
comparison (JSON + Excel), selection, and clarification drafts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.models.package import Package
from app.models.supplier import Supplier
from app.schemas.email import EmailLogResponse
from app.schemas.offer import (
    ClarificationRequest,
    ComparisonResponse,
    OfferCommercialUpdate,
    OfferDetailResponse,
    OfferResponse,
    ScorePackageResult,
)
from app.services.email.rfq_service import RFQService
from app.services.offer.comparison_export import export_comparison_excel
from app.services.offer.offer_extractor import LLMUnavailable, OfferExtractor
from app.services.offer.offer_service import OfferService
from app.services.offer.scoring_service import ScoringService

router = APIRouter(tags=["offers"])


async def _require_package(db: AsyncSession, project_id: int, package_id: int) -> Package:
    package = await db.get(Package, package_id)
    if package is None or package.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    return package


async def _detail(db: AsyncSession, offer) -> OfferDetailResponse:
    supplier = await db.get(Supplier, offer.supplier_id)
    base = OfferResponse.model_validate(offer)
    return OfferDetailResponse(
        **base.model_dump(),
        supplier_name=supplier.name if supplier else None,
        vat_included=offer.vat_included,
        exclusions=offer.exclusions,
        deviations=offer.deviations,
        missing_items=offer.missing_items,
        clarifications_needed=offer.clarifications_needed,
        compliance_analysis=offer.compliance_analysis,
        line_items=offer.line_items,
        evaluator_notes=offer.evaluator_notes,
        recommendation=offer.recommendation,
    )


def _safe_filename(name: str | None) -> str:
    return Path(name or "offer").name or "offer"


@router.post(
    "/projects/{project_id}/packages/{package_id}/offers",
    response_model=OfferResponse,
    status_code=201,
)
async def ingest_offer(
    project_id: int,
    package_id: int,
    supplier_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> OfferResponse:
    await _require_package(db, project_id, package_id)
    if await db.get(Supplier, supplier_id) is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    dest = Path("data") / "offers" / f"pkg_{package_id}" / f"sup_{supplier_id}"
    dest.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for upload in files:
        target = dest / _safe_filename(upload.filename)
        target.write_bytes(await upload.read())
        saved.append(str(target))
    offer = await OfferService().create_offer(db, package_id, supplier_id, saved)
    return OfferResponse.model_validate(offer)


@router.get(
    "/projects/{project_id}/packages/{package_id}/offers",
    response_model=list[OfferResponse],
)
async def list_offers(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> list[OfferResponse]:
    await _require_package(db, project_id, package_id)
    offers = await OfferService().list_offers(db, package_id)
    return [OfferResponse.model_validate(o) for o in offers]


@router.post(
    "/projects/{project_id}/packages/{package_id}/offers/score",
    response_model=ScorePackageResult,
)
async def score_offers(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> ScorePackageResult:
    await _require_package(db, project_id, package_id)
    return ScorePackageResult(**await ScoringService().score_package(db, package_id))


@router.get(
    "/projects/{project_id}/packages/{package_id}/offers/comparison",
    response_model=ComparisonResponse,
)
async def comparison(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
) -> ComparisonResponse:
    await _require_package(db, project_id, package_id)
    return ComparisonResponse(**await ScoringService().compare(db, package_id))


@router.get("/projects/{project_id}/packages/{package_id}/offers/comparison.xlsx")
async def comparison_xlsx(
    project_id: int, package_id: int, db: AsyncSession = Depends(get_db)
):
    await _require_package(db, project_id, package_id)
    data = await ScoringService().compare(db, package_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        out = tmp.name
    export_comparison_excel(data, out)
    return FileResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"comparison_package_{package_id}.xlsx",
        background=BackgroundTask(lambda: Path(out).unlink(missing_ok=True)),
    )


@router.get("/offers/{offer_id}", response_model=OfferDetailResponse)
async def get_offer(offer_id: int, db: AsyncSession = Depends(get_db)) -> OfferDetailResponse:
    offer = await OfferService().get_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return await _detail(db, offer)


@router.patch("/offers/{offer_id}", response_model=OfferDetailResponse)
async def update_offer(
    offer_id: int, payload: OfferCommercialUpdate, db: AsyncSession = Depends(get_db)
) -> OfferDetailResponse:
    offer = await OfferService().update_commercial(
        db, offer_id, **payload.model_dump(exclude_unset=True)
    )
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/extract", response_model=OfferDetailResponse)
async def extract_offer(offer_id: int, db: AsyncSession = Depends(get_db)) -> OfferDetailResponse:
    try:
        await OfferExtractor().extract_offer(db, offer_id)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    offer = await OfferService().get_offer(db, offer_id)
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/check-compliance", response_model=OfferDetailResponse)
async def check_compliance(offer_id: int, db: AsyncSession = Depends(get_db)) -> OfferDetailResponse:
    try:
        await OfferExtractor().check_compliance(db, offer_id)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    offer = await OfferService().get_offer(db, offer_id)
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/select", response_model=OfferDetailResponse)
async def select_offer(
    offer_id: int, payload: dict | None = None, db: AsyncSession = Depends(get_db)
) -> OfferDetailResponse:
    notes = (payload or {}).get("notes")
    offer = await OfferService().select_offer(db, offer_id, notes=notes)
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
    return await _detail(db, offer)


@router.post("/offers/{offer_id}/clarification", response_model=EmailLogResponse, status_code=201)
async def create_clarification(
    offer_id: int, payload: ClarificationRequest, db: AsyncSession = Depends(get_db)
) -> EmailLogResponse:
    try:
        draft = await RFQService().create_clarification_drafts(
            db, offer_id, items=payload.items, language=payload.language,
            response_days=payload.response_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EmailLogResponse.model_validate(draft)
```

> **Route-ordering note:** the three package-level sub-routes (`/offers/score`, `/offers/comparison`, `/offers/comparison.xlsx`) are declared **before** `GET /offers/{offer_id}` and live under the `/projects/.../packages/...` prefix, so there is no `{offer_id}` capture collision. Keep `OfferExtractor` imported at module top so the 503 test can monkeypatch `app.api.offers.OfferExtractor`.

- [ ] **Step 4: Register the router in `app/main.py`**

Add the import (after `offers`/`emails` style imports — alphabetical block is fine):

```python
from app.api.offers import router as offers_router
```

Add the registration after the emails router:

```python
app.include_router(offers_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/offers/test_offers_api.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/offers.py app/main.py tests/offers/test_offers_api.py
git commit -m "feat(phase-10): offers API — ingest, score, comparison(+xlsx), extract/compliance(503), select, clarification"
```

---

## Task 8: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, zero failures, no new skips. Baseline was 106; this phase adds ~5 (offer service) + 4 (scoring) + 1 (export) + 5 (extractor) + 4 (clarification: 2 template + 2 rfq) + 6 (offers API) = **~25** → roughly **131 passing** (±a couple if cases were split/merged; the hard requirement is zero failures).

- [ ] **Step 2: Smoke-check routes register**

Run:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'offer' in p or 'clarification' in p or 'comparison' in p))"
```
Expected to include (order may differ):
```
/api/offers/{offer_id}
/api/offers/{offer_id}/check-compliance
/api/offers/{offer_id}/clarification
/api/offers/{offer_id}/extract
/api/offers/{offer_id}/select
/api/projects/{project_id}/packages/{package_id}/offers
/api/projects/{project_id}/packages/{package_id}/offers/comparison
/api/projects/{project_id}/packages/{package_id}/offers/comparison.xlsx
/api/projects/{project_id}/packages/{package_id}/offers/score
```

- [ ] **Step 3: Final commit (if anything uncommitted)**

```bash
git add -A
git commit -m "test(phase-10): full suite green — offer evaluation + comparison"
```

---

## Spec Coverage Self-Review

| Phase 10 spec requirement (spec §6 caps 7,8) | Task |
|---|---|
| Offer ingest (upload + register files) | 2, 7 |
| Manual commercial data entry (works without LLM) | 2, 7 |
| AI offer-data extraction | 1, 5, 7 |
| Compliance vs checklist | 1, 5, 7 |
| Configurable weighted scoring + ranking | 3, 7 |
| Offer comparison data + matrix Excel | 3, 4, 7 |
| Clarification-email drafts | 6, 7 |
| Winner selection | 2, 7 |
| Graceful degradation when LLM/key absent | 5 (`LLMUnavailable`), 7 (503) |
| Configurable market (weights/thresholds/currency from rules) | 3 |
| Root conventions (`.value` enums, no lazy loads, db param, no JSON `.contains`) | all |

**Deferred / out of scope (intentionally):** award/regret letters (Phase 14); offer line-item → BOQ price population (Phase 11 pricing); a React UI for these screens (Phase 6C); real LLM enablement (blocked on a valid Gemini key — see the gemini-key-status memory). The `payment_terms` sub-score is a documented neutral constant (50) because it is not objectively computable from stored data; it can be upgraded to a manual sub-score in a later phase without changing the scoring contract.
