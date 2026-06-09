# Phase 11 — BOQ Pricing (formula-preserving) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate BOQ item prices from a selected supplier offer (fuzzy line-item mapping), apply configurable markups + VAT to produce a cost→selling pricing summary, surface a gaps/risk report, allow manual per-item price overrides, and write the prices back into the client's original Excel template **without destroying its formulas**.

**Architecture:** All pure logic except the LLM-free fuzzy matcher and an openpyxl template writer — nothing in this phase needs a Gemini key. `PricingService` (rules-injectable) maps each package BOQ item to the best-matching offer line item via a deterministic fuzzy matcher (`line_item_matcher`), writes `unit_rate`/`total_price`/`mapping_confidence` onto `BOQItem`, and computes a rules-driven pricing summary (markups from `rules.commercial.markup`, VAT from `rules.commercial.vat_rate`, currency from `rules.commercial.currency`). Formula-preserving population re-accepts the client template (it is not retained at parse time) and uses openpyxl loaded WITHOUT `data_only`/`read_only` so formula cells are preserved as strings; only the detected rate column is written, addressed by each item's `client_row_index` (the 1-based Excel row captured by the Phase 7 parser). Root conventions hold: services take `db: AsyncSession`; enums compared as `.value`; responses built from explicitly-loaded children (no lazy load → no `MissingGreenlet`); no SQLAlchemy JSON `.contains()`.

**Tech Stack:** FastAPI · async SQLAlchemy 2.0 + aiosqlite · openpyxl (template read+write, formula-preserving) · stdlib `difflib`/`re` (fuzzy matching — no extra deps) · pytest-asyncio + httpx ASGITransport.

**No database migration is required** — `BOQItem` already has every pricing field (`selected_offer_id`, `unit_rate`, `total_price`, `currency`, `mapping_confidence`, `requires_review`, `review_notes`, `is_excluded`, `client_ref`, `client_row_index`). This phase adds no columns.

---

## Pre-flight (read, do not skip)

1. **`client_row_index` is the 1-based Excel row** captured by `app/services/boq/boq_parser.py` (`client_row_index=r`). Formula-preserving population writes the rate into cell `(client_row_index, rate_col)` of the re-uploaded template. Items can have `client_row_index = None` (rare) — skip those for template writing.
2. **The original BOQ file is NOT retained** (parsed in a `tempfile.TemporaryDirectory`). The template-population endpoint therefore re-accepts the client `.xlsx` upload. Do NOT try to read a stored original.
3. **openpyxl formula preservation:** `load_workbook(path)` (NOT `read_only`, NOT `data_only=True`) keeps formula cells as their `=...` strings. Writing a value into the rate column leaves the total column's `=qty*rate` formula intact (Excel recalculates on open; openpyxl does not, and that's fine). Use `data_only=False` (the default) when re-reading in tests to assert the formula string survived.
4. **The parser does not detect a rate/price column** (its aliases are item/description/unit/quantity/section only). The template writer must detect the rate column by header aliases (`rate`, `unit rate`, `unit price`, ...), with an optional explicit override.
5. **Offer line items** are dicts shaped `{"description", "unit", "quantity", "rate", "total"}` (see `OfferLineItem` in `app/schemas/offer.py`; `OfferExtractor` persists `li.model_dump()`). Read the rate via `item.get("rate")` (fall back to `item.get("unit_rate")`).
6. **Only a SELECTED offer prices a package.** `SupplierOffer.status` stores an `OfferStatus` value string; compare `offer.status == OfferStatus.SELECTED.value`.
7. **Services take `db` as a param**; build nested responses from explicit queries. `RulesService` is injectable (default `RulesService()`), matching Phase 9/10. `BOQItem.quantity` is a non-null float; `total_price = round(unit_rate * quantity, 2)`.
8. **Markup model (documented, configurable):** each of `rules.commercial.markup.{overhead, profit, contingency, risk}` is a fraction applied to the cost subtotal; `markup_total = cost × Σ(fractions)`; `selling_before_vat = cost + markup_total`; `vat_amount = selling_before_vat × rules.commercial.vat_rate`; `grand_total = selling_before_vat + vat_amount`.

Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (must stay green; baseline = **143 passing**).

---

## File Structure

**Create:**
- `app/schemas/pricing.py` — pricing request/response models.
- `app/services/pricing/__init__.py`
- `app/services/pricing/line_item_matcher.py` — pure fuzzy matcher (`normalize_desc`, `match_score`, `best_match`).
- `app/services/pricing/pricing_service.py` — `PricingService` (populate-from-offer, summary, gaps, manual update).
- `app/services/pricing/template_writer.py` — `populate_template` (formula-preserving openpyxl write) + rate-column detection.
- `app/api/pricing.py` — pricing router.
- `tests/pricing/__init__.py`, `tests/pricing/test_line_item_matcher.py`, `tests/pricing/test_pricing_service.py`, `tests/pricing/test_template_writer.py`, `tests/pricing/test_pricing_api.py`

**Modify:**
- `app/main.py` — register `pricing_router`.

---

## Task 1: Pricing schemas + fuzzy line-item matcher

**Files:**
- Create: `app/schemas/pricing.py`, `app/services/pricing/__init__.py`, `app/services/pricing/line_item_matcher.py`
- Test: `tests/pricing/__init__.py`, `tests/pricing/test_line_item_matcher.py`

- [ ] **Step 1: Write the schemas**

Create `app/schemas/pricing.py`:

```python
"""Schemas for BOQ pricing: population results, summary, gaps, manual update."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PricePopulationResult(BaseModel):
    offer_id: int
    package_id: int
    items_populated: int
    items_needs_review: int
    items_unmatched: int
    total_value: float
    currency: str | None = None
    markup_applied: bool


class TradePricing(BaseModel):
    trade: str
    count: int
    total: float
    percentage: float


class MarkupBreakdown(BaseModel):
    overhead: float
    profit: float
    contingency: float
    risk: float
    markup_total: float


class PricingSummary(BaseModel):
    project_id: int
    currency: str
    total_items: int
    priced_items: int
    unpriced_items: int
    completion_rate: float
    cost_subtotal: float
    markups: MarkupBreakdown
    selling_before_vat: float
    vat_rate: float
    vat_amount: float
    grand_total: float
    by_trade: list[TradePricing] = Field(default_factory=list)


class GapItem(BaseModel):
    id: int
    line_number: str | None = None
    description: str
    trade_category: str | None = None
    reason: str


class GapsReport(BaseModel):
    project_id: int
    unpriced_count: int
    needs_review_count: int
    excluded_count: int
    unpriced: list[GapItem] = Field(default_factory=list)
    needs_review: list[GapItem] = Field(default_factory=list)
    excluded: list[GapItem] = Field(default_factory=list)


class ItemPriceUpdate(BaseModel):
    unit_rate: float
    notes: str | None = None


class BOQItemPriceResponse(BaseModel):
    id: int
    line_number: str | None = None
    description: str
    unit: str | None = None
    quantity: float
    unit_rate: float | None = None
    total_price: float | None = None
    currency: str | None = None
    mapping_confidence: float | None = None
    requires_review: bool
    is_excluded: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing matcher tests**

Create `tests/pricing/__init__.py` (empty file).

Create `tests/pricing/test_line_item_matcher.py`:

```python
from app.services.pricing.line_item_matcher import best_match, match_score, normalize_desc


def test_normalize_strips_punctuation_and_case():
    assert normalize_desc("Supply & Install (Chiller)!") == "supply install chiller"


def test_identical_descriptions_score_1():
    assert match_score("Concrete grade C30", "concrete grade c30") == 1.0


def test_reordered_words_score_high():
    s = match_score("Split AC unit supply and installation",
                    "Supply and install split AC unit")
    assert s >= 0.6


def test_unrelated_descriptions_score_low():
    assert match_score("Concrete C30 foundation", "Split AC indoor unit") < 0.3


def test_empty_scores_zero():
    assert match_score("", "anything") == 0.0


def test_best_match_picks_highest_above_threshold():
    candidates = [
        {"description": "VRF outdoor condensing unit", "rate": 8000},
        {"description": "Split AC unit supply and installation", "rate": 1200},
    ]
    item, score = best_match("Split AC unit (supply & install)", candidates, threshold=0.45)
    assert item is not None
    assert item["rate"] == 1200
    assert score >= 0.45


def test_best_match_returns_none_below_threshold():
    candidates = [{"description": "Asphalt road base", "rate": 50}]
    item, score = best_match("Curtain wall glazing", candidates, threshold=0.45)
    assert item is None


def test_best_match_uses_semantic_scorer_when_higher():
    candidates = [{"description": "totally different text", "rate": 99}]
    # fuzzy score is ~0; injected semantic scorer forces a match
    item, score = best_match(
        "anything", candidates, threshold=0.45,
        semantic_scorer=lambda a, b: 0.9,
    )
    assert item is not None and score == 0.9
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_line_item_matcher.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.pricing`.

- [ ] **Step 4: Implement the matcher**

Create `app/services/pricing/__init__.py` (empty file).

Create `app/services/pricing/line_item_matcher.py`:

```python
"""Deterministic fuzzy matching of BOQ item descriptions to offer line items.

No LLM/embeddings — combines token-set Jaccard with difflib's sequence ratio.
An optional semantic_scorer(a, b) -> float can be injected to blend in an
embedding-based score (the seam for a future semantic upgrade); when absent the
matcher is fully deterministic and dependency-free.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Default match threshold for accepting a BOQ<->offer line-item pairing, and the
# confidence above which a populated price is NOT flagged for review.
DEFAULT_THRESHOLD = 0.45
HIGH_CONFIDENCE = 0.7

_PUNCT = re.compile(r"[^\w\s]")


def normalize_desc(text: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    cleaned = _PUNCT.sub(" ", str(text).lower())
    return " ".join(cleaned.split())


def match_score(a: str | None, b: str | None) -> float:
    """Similarity in [0, 1]: mean of token-set Jaccard and difflib ratio."""
    na, nb = normalize_desc(a), normalize_desc(b)
    if not na or not nb:
        return 0.0
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / len(ta | tb)
    ratio = SequenceMatcher(None, na, nb).ratio()
    return round((jaccard + ratio) / 2.0, 4)


def best_match(
    query: str,
    candidates: list[dict],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    semantic_scorer=None,
    key: str = "description",
) -> tuple[dict | None, float]:
    """Return (best candidate, score) if score >= threshold, else (None, score)."""
    best: dict | None = None
    best_score = 0.0
    for cand in candidates:
        cand_desc = cand.get(key, "") if isinstance(cand, dict) else getattr(cand, key, "")
        score = match_score(query, cand_desc)
        if semantic_scorer is not None:
            score = max(score, float(semantic_scorer(query, cand_desc)))
        if score > best_score:
            best_score = score
            best = cand
    if best_score >= threshold:
        return best, round(best_score, 4)
    return None, round(best_score, 4)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_line_item_matcher.py -q`
Expected: PASS (8 tests).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/pricing.py app/services/pricing/__init__.py app/services/pricing/line_item_matcher.py tests/pricing/__init__.py tests/pricing/test_line_item_matcher.py
git commit -m "feat(phase-11): pricing schemas + deterministic fuzzy line-item matcher"
```

---

## Task 2: PricingService.populate_from_offer

**Files:**
- Create: `app/services/pricing/pricing_service.py`
- Test: `tests/pricing/test_pricing_service.py`

Maps each package BOQ item to the best offer line item and writes `unit_rate`/`total_price`/`mapping_confidence`/`selected_offer_id`. Optional markup uplift (sum of `rules.commercial.markup` fractions). Unmatched items are flagged `requires_review` with a note.

- [ ] **Step 1: Write the failing tests**

Create `tests/pricing/test_pricing_service.py`:

```python
import pytest

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.pricing.pricing_service import PricingService


async def _seed_priced(db, *, offer_status=OfferStatus.SELECTED.value, line_items=None):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP", trade_category="mep")
    db.add(package)
    await db.flush()
    descs = [
        ("Split AC unit supply & installation", "no", 5, "mep"),
        ("VRF outdoor condensing unit", "no", 2, "mep"),
        ("Builders work in connection", "ls", 1, "civil"),
    ]
    items = []
    for i, (d, u, q, trade) in enumerate(descs, start=1):
        it = BOQItem(project_id=project.id, package_id=package.id, line_number=str(i),
                     description=d, unit=u, quantity=q, client_row_index=i + 1,
                     trade_category=trade)
        db.add(it)
        items.append(it)
    supplier = Supplier(name="CoolAir", emails=[], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    offer = SupplierOffer(
        package_id=package.id, supplier_id=supplier.id, status=offer_status,
        file_paths=[], currency="USD",
        line_items=line_items if line_items is not None else [
            {"description": "Supply and install split AC unit", "rate": 1200, "unit": "no"},
            {"description": "VRF outdoor condensing unit", "rate": 8000, "unit": "no"},
        ],
    )
    db.add(offer)
    await db.commit()
    for o in items + [offer, package]:
        await db.refresh(o)
    return package, offer, items


async def test_populate_maps_and_prices(db_session):
    package, offer, items = await _seed_priced(db_session)
    result = await PricingService().populate_from_offer(db_session, offer.id)
    assert result["items_populated"] == 2
    assert result["items_unmatched"] == 1
    assert result["total_value"] == 1200 * 5 + 8000 * 2  # 22000
    assert result["currency"] == "USD"
    await db_session.refresh(items[0])
    assert items[0].unit_rate == 1200
    assert items[0].total_price == 6000
    assert items[0].selected_offer_id == offer.id
    assert items[0].mapping_confidence is not None
    await db_session.refresh(items[2])
    assert items[2].unit_rate is None
    assert items[2].requires_review is True


async def test_populate_applies_markup(db_session):
    package, offer, items = await _seed_priced(db_session)
    result = await PricingService().populate_from_offer(db_session, offer.id, apply_markup=True)
    assert result["markup_applied"] is True
    await db_session.refresh(items[0])
    # default markup sum = 0.10+0.08+0.05+0.03 = 0.26 -> rate 1200*1.26 = 1512
    assert items[0].unit_rate == 1512.0
    assert items[0].total_price == round(1512.0 * 5, 2)


async def test_populate_rejects_unselected_offer(db_session):
    package, offer, items = await _seed_priced(db_session, offer_status=OfferStatus.RECEIVED.value)
    with pytest.raises(ValueError):
        await PricingService().populate_from_offer(db_session, offer.id)


async def test_populate_rejects_offer_without_line_items(db_session):
    package, offer, items = await _seed_priced(db_session, line_items=[])
    with pytest.raises(ValueError):
        await PricingService().populate_from_offer(db_session, offer.id)


async def test_populate_unknown_offer(db_session):
    with pytest.raises(ValueError):
        await PricingService().populate_from_offer(db_session, 999999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_pricing_service.py -q`
Expected: FAIL — `ModuleNotFoundError: ...pricing_service`.

- [ ] **Step 3: Implement `populate_from_offer`**

Create `app/services/pricing/pricing_service.py`:

```python
"""BOQ pricing: populate from offers, summarize with markups, report gaps.

Pure DB/logic — no LLM. Mapping uses the deterministic fuzzy matcher; an
optional semantic_scorer can be injected for a future embedding-based blend.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.supplier import SupplierOffer
from app.services.pricing.line_item_matcher import (
    DEFAULT_THRESHOLD,
    HIGH_CONFIDENCE,
    best_match,
)
from app.services.rules.rules_service import RulesService


class PricingService:
    def __init__(self, rules_service: RulesService | None = None, semantic_scorer=None) -> None:
        self._rules_service = rules_service or RulesService()
        self._semantic_scorer = semantic_scorer

    def _rules(self):
        return self._rules_service.load()

    def _markup_factor(self) -> float:
        m = self._rules().commercial.markup
        return 1.0 + (m.overhead + m.profit + m.contingency + m.risk)

    async def populate_from_offer(
        self,
        db: AsyncSession,
        offer_id: int,
        *,
        apply_markup: bool = False,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> dict:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        if offer.status != OfferStatus.SELECTED.value:
            raise ValueError("Only a selected offer can price a package")
        line_items = offer.line_items or []
        if not line_items:
            raise ValueError("Offer has no line items to populate from")

        boq_items = list(
            (
                await db.execute(
                    select(BOQItem)
                    .where(BOQItem.package_id == offer.package_id)
                    .order_by(BOQItem.client_row_index, BOQItem.id)
                )
            ).scalars().all()
        )
        factor = self._markup_factor() if apply_markup else 1.0

        populated = needs_review = unmatched = 0
        total_value = 0.0
        for item in boq_items:
            match, score = best_match(
                item.description, line_items,
                threshold=threshold, semantic_scorer=self._semantic_scorer,
            )
            if match is None:
                item.requires_review = True
                item.review_notes = "No offer line item matched this BOQ item"
                unmatched += 1
                continue
            rate = float(match.get("rate") or match.get("unit_rate") or 0.0)
            if rate <= 0:
                item.requires_review = True
                item.review_notes = "Matched offer line item has no usable rate"
                unmatched += 1
                continue
            rate *= factor
            item.unit_rate = round(rate, 2)
            item.total_price = round(rate * item.quantity, 2)
            item.currency = offer.currency
            item.selected_offer_id = offer.id
            item.mapping_confidence = score
            item.requires_review = score < HIGH_CONFIDENCE
            if item.requires_review:
                item.review_notes = f"Low-confidence price mapping ({score})"
                needs_review += 1
            else:
                item.review_notes = None
            total_value += item.total_price
            populated += 1

        await db.commit()
        return {
            "offer_id": offer_id,
            "package_id": offer.package_id,
            "items_populated": populated,
            "items_needs_review": needs_review,
            "items_unmatched": unmatched,
            "total_value": round(total_value, 2),
            "currency": offer.currency,
            "markup_applied": apply_markup,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_pricing_service.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/pricing/pricing_service.py tests/pricing/test_pricing_service.py
git commit -m "feat(phase-11): PricingService.populate_from_offer — fuzzy map + optional markup"
```

---

## Task 3: Pricing summary, gaps report, manual price update

**Files:**
- Modify: `app/services/pricing/pricing_service.py`
- Test: `tests/pricing/test_pricing_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/pricing/test_pricing_service.py`:

```python
async def test_pricing_summary_markups_and_vat(db_session):
    package, offer, items = await _seed_priced(db_session)
    await PricingService().populate_from_offer(db_session, offer.id)
    summary = await PricingService().pricing_summary(db_session, package.project_id)
    assert summary["cost_subtotal"] == 22000.0
    assert summary["priced_items"] == 2
    assert summary["unpriced_items"] == 1
    # default markups: overhead .08, profit .10, contingency .05, risk .03 -> total .26
    assert summary["markups"]["markup_total"] == round(22000.0 * 0.26, 2)
    assert summary["selling_before_vat"] == round(22000.0 * 1.26, 2)
    # default vat_rate 0.0
    assert summary["vat_amount"] == 0.0
    assert summary["grand_total"] == round(22000.0 * 1.26, 2)
    assert summary["currency"] == "USD"
    trades = {t["trade"]: t for t in summary["by_trade"]}
    assert trades["mep"]["total"] == 22000.0


async def test_pricing_summary_respects_rules_vat(db_session):
    from app.schemas.rules import RulesConfig

    class _FakeRules:
        def __init__(self):
            self._cfg = RulesConfig()
            self._cfg.commercial.vat_rate = 0.10
            self._cfg.commercial.currency = "EGP"

        def load(self):
            return self._cfg

    package, offer, items = await _seed_priced(db_session)
    svc = PricingService(rules_service=_FakeRules())
    await svc.populate_from_offer(db_session, offer.id)
    summary = await svc.pricing_summary(db_session, package.project_id)
    selling = round(22000.0 * 1.26, 2)
    assert summary["vat_rate"] == 0.10
    assert summary["vat_amount"] == round(selling * 0.10, 2)
    assert summary["grand_total"] == round(selling * 1.10, 2)
    assert summary["currency"] == "EGP"


async def test_gaps_report(db_session):
    package, offer, items = await _seed_priced(db_session)
    await PricingService().populate_from_offer(db_session, offer.id)
    # exclude one of the priced items to exercise that bucket
    items[1].is_excluded = True
    await db_session.commit()
    report = await PricingService().gaps_report(db_session, package.project_id)
    # item[2] (Builders work) was unmatched -> unpriced & needs_review
    assert report["unpriced_count"] >= 1
    assert any(g["id"] == items[2].id for g in report["unpriced"])
    assert report["excluded_count"] == 1
    assert any(g["id"] == items[1].id for g in report["excluded"])


async def test_update_item_price(db_session):
    package, offer, items = await _seed_priced(db_session)
    svc = PricingService()
    updated = await svc.update_item_price(db_session, items[2].id, 450.0, notes="manual")
    assert updated.unit_rate == 450.0
    assert updated.total_price == 450.0  # quantity 1
    assert updated.requires_review is False
    assert await svc.update_item_price(db_session, 999999, 1.0) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_pricing_service.py -q -k "summary or gaps or update_item"`
Expected: FAIL — `AttributeError: 'PricingService' object has no attribute 'pricing_summary'`.

- [ ] **Step 3: Implement the three methods**

Append to the `PricingService` class in `app/services/pricing/pricing_service.py`:

```python
    async def pricing_summary(self, db: AsyncSession, project_id: int) -> dict:
        items = list(
            (
                await db.execute(select(BOQItem).where(BOQItem.project_id == project_id))
            ).scalars().all()
        )
        rules = self._rules()
        priced = [i for i in items if i.total_price]
        cost_subtotal = round(sum(i.total_price for i in priced), 2)

        m = rules.commercial.markup
        overhead = round(cost_subtotal * m.overhead, 2)
        profit = round(cost_subtotal * m.profit, 2)
        contingency = round(cost_subtotal * m.contingency, 2)
        risk = round(cost_subtotal * m.risk, 2)
        markup_total = round(overhead + profit + contingency + risk, 2)
        selling_before_vat = round(cost_subtotal + markup_total, 2)
        vat_rate = rules.commercial.vat_rate
        vat_amount = round(selling_before_vat * vat_rate, 2)
        grand_total = round(selling_before_vat + vat_amount, 2)

        by_trade: dict[str, dict] = {}
        for i in priced:
            trade = i.trade_category or "uncategorized"
            bucket = by_trade.setdefault(trade, {"count": 0, "total": 0.0})
            bucket["count"] += 1
            bucket["total"] += i.total_price
        by_trade_list = [
            {
                "trade": trade,
                "count": data["count"],
                "total": round(data["total"], 2),
                "percentage": round(data["total"] / cost_subtotal * 100, 1) if cost_subtotal else 0.0,
            }
            for trade, data in sorted(by_trade.items(), key=lambda kv: -kv[1]["total"])
        ]

        currency = next((i.currency for i in priced if i.currency), rules.commercial.currency)
        return {
            "project_id": project_id,
            "currency": currency,
            "total_items": len(items),
            "priced_items": len(priced),
            "unpriced_items": len(items) - len(priced),
            "completion_rate": round(len(priced) / len(items) * 100, 1) if items else 0.0,
            "cost_subtotal": cost_subtotal,
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
            "by_trade": by_trade_list,
        }

    async def gaps_report(self, db: AsyncSession, project_id: int) -> dict:
        items = list(
            (
                await db.execute(select(BOQItem).where(BOQItem.project_id == project_id))
            ).scalars().all()
        )

        def gap(item, reason: str) -> dict:
            return {
                "id": item.id,
                "line_number": item.line_number,
                "description": item.description,
                "trade_category": item.trade_category,
                "reason": reason,
            }

        unpriced = [gap(i, i.review_notes or "No price") for i in items if not i.total_price and not i.is_excluded]
        needs_review = [
            gap(i, i.review_notes or f"Low-confidence mapping ({i.mapping_confidence})")
            for i in items if i.requires_review and not i.is_excluded
        ]
        excluded = [gap(i, i.exclusion_reason or "Excluded from pricing") for i in items if i.is_excluded]
        return {
            "project_id": project_id,
            "unpriced_count": len(unpriced),
            "needs_review_count": len(needs_review),
            "excluded_count": len(excluded),
            "unpriced": unpriced,
            "needs_review": needs_review,
            "excluded": excluded,
        }

    async def update_item_price(
        self, db: AsyncSession, item_id: int, unit_rate: float, notes: str | None = None
    ) -> BOQItem | None:
        item = await db.get(BOQItem, item_id)
        if item is None:
            return None
        item.unit_rate = round(unit_rate, 2)
        item.total_price = round(unit_rate * item.quantity, 2)
        item.requires_review = False
        item.review_notes = notes
        await db.commit()
        await db.refresh(item)
        return item
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_pricing_service.py -q`
Expected: PASS (all, including the 4 new tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/pricing/pricing_service.py tests/pricing/test_pricing_service.py
git commit -m "feat(phase-11): pricing summary (markups+VAT), gaps report, manual price override"
```

---

## Task 4: Formula-preserving client-template writer

**Files:**
- Create: `app/services/pricing/template_writer.py`
- Test: `tests/pricing/test_template_writer.py`

Re-accepts the client `.xlsx`, detects the rate column by header alias (or explicit override), and writes each item's `unit_rate` into `(client_row_index, rate_col)` while leaving every formula cell untouched.

- [ ] **Step 1: Write the failing test**

Create `tests/pricing/test_template_writer.py`:

```python
import openpyxl
import pytest

from app.services.pricing.template_writer import detect_rate_column, populate_template


def _make_template(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Item", "Description", "Unit", "Qty", "Rate", "Amount"])  # row 1 header
    # row 2 and row 3 data; Amount has a formula referencing Qty*Rate
    ws.append([1, "Split AC unit", "no", 5, None, "=D2*E2"])
    ws.append([2, "VRF unit", "no", 2, None, "=D3*E3"])
    wb.save(path)
    return str(path)


def test_detect_rate_column():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty", "Unit Rate", "Amount"])
    assert detect_rate_column(ws) == 5


def test_populate_writes_rates_and_preserves_formulas(tmp_path):
    src = _make_template(tmp_path / "client.xlsx")
    out = str(tmp_path / "out.xlsx")
    result = populate_template(src, out, {2: 1200.0, 3: 8000.0})
    assert result["written"] == 2
    assert result["rate_column"] == 5
    wb = openpyxl.load_workbook(out)  # data_only=False -> formulas kept as strings
    ws = wb["BOQ"]
    assert ws.cell(row=2, column=5).value == 1200.0
    assert ws.cell(row=3, column=5).value == 8000.0
    # the Amount column formulas must survive untouched
    assert ws.cell(row=2, column=6).value == "=D2*E2"
    assert ws.cell(row=3, column=6).value == "=D3*E3"


def test_populate_explicit_rate_column(tmp_path):
    src = _make_template(tmp_path / "c.xlsx")
    out = str(tmp_path / "o.xlsx")
    result = populate_template(src, out, {2: 99.0}, rate_column=5)
    assert result["written"] == 1
    wb = openpyxl.load_workbook(out)
    assert wb["BOQ"].cell(row=2, column=5).value == 99.0


def test_populate_raises_when_no_rate_column(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Qty"])  # no rate-like header
    ws.append([1, "x", 3])
    p = tmp_path / "norate.xlsx"
    wb.save(p)
    with pytest.raises(ValueError):
        populate_template(str(p), str(tmp_path / "o.xlsx"), {2: 10.0})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_template_writer.py -q`
Expected: FAIL — `ModuleNotFoundError: ...template_writer`.

- [ ] **Step 3: Implement the writer**

Create `app/services/pricing/template_writer.py`:

```python
"""Write BOQ unit rates back into the client's Excel template, formula-preserving.

The workbook is loaded with openpyxl's defaults (NOT read_only, NOT
data_only) so every formula cell is preserved verbatim as its "=..." string.
Only the detected rate column is written, addressed by each item's
client_row_index (1-based Excel row), so total/amount formulas keep working
(Excel recalculates them on open).
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

# Header aliases that identify the (empty) rate / unit-price column to fill.
_RATE_ALIASES = (
    "rate", "unit rate", "unit price", "unitprice", "unit_rate",
    "u.rate", "u rate", "u.price", "price", "rate (usd)", "unit rate (usd)",
)
_SHEET_HINTS = ("boq", "bill", "quantity", "pricing", "boqs")
_MAX_HEADER_SCAN = 20


def _pick_sheet(wb):
    for name in wb.sheetnames:
        if any(h in name.lower() for h in _SHEET_HINTS):
            return wb[name]
    return wb[wb.sheetnames[0]]


def _norm(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def detect_rate_column(ws) -> int | None:
    """Return the 1-based column index of the rate header, or None."""
    for r in range(1, min(ws.max_row, _MAX_HEADER_SCAN) + 1):
        for c in range(1, ws.max_column + 1):
            if _norm(ws.cell(row=r, column=c).value) in _RATE_ALIASES:
                return c
    return None


def populate_template(
    template_path: str,
    output_path: str,
    row_rates: dict[int, float],
    rate_column: int | None = None,
) -> dict:
    """Write rates into the rate column at the given 1-based rows; keep formulas.

    Args:
        template_path: the client's original .xlsx.
        output_path: where to write the populated copy.
        row_rates: {client_row_index (1-based) -> unit_rate}.
        rate_column: optional explicit 1-based rate column (else auto-detected).

    Returns: {"written": int, "rate_column": int}.
    Raises ValueError if the rate column cannot be determined.
    """
    wb = load_workbook(template_path)  # defaults preserve formulas
    try:
        ws = _pick_sheet(wb)
        col = rate_column or detect_rate_column(ws)
        if col is None:
            raise ValueError(
                "Could not detect a rate column in the template; pass rate_column explicitly"
            )
        written = 0
        for row_idx, rate in row_rates.items():
            if row_idx is None:
                continue
            ws.cell(row=row_idx, column=col, value=rate)
            written += 1
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return {"written": written, "rate_column": col}
    finally:
        wb.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_template_writer.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/pricing/template_writer.py tests/pricing/test_template_writer.py
git commit -m "feat(phase-11): formula-preserving client-template rate writer"
```

---

## Task 5: Pricing API router

**Files:**
- Create: `app/api/pricing.py`
- Modify: `app/main.py`
- Test: `tests/pricing/test_pricing_api.py`

Endpoints:
- `POST  /api/offers/{offer_id}/populate-prices?apply_markup=bool` — price the offer's package from that selected offer.
- `GET   /api/projects/{pid}/pricing/summary` — cost → markups → VAT → grand total.
- `GET   /api/projects/{pid}/pricing/gaps` — unpriced / needs-review / excluded.
- `PATCH /api/boq-items/{item_id}/price` — manual unit-rate override.
- `POST  /api/projects/{pid}/pricing/populate-template` — multipart upload the client `.xlsx`; returns the populated, formula-preserving copy as a download.

- [ ] **Step 1: Write the failing tests**

Create `tests/pricing/test_pricing_api.py`:

```python
import io

import httpx
import openpyxl
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def pricing_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.base import OfferStatus
    from app.models.boq import BOQItem
    from app.models.package import Package
    from app.models.project import Project
    from app.models.supplier import Supplier, SupplierOffer

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
        await seed.flush()
        seed.add_all([
            BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                    description="Split AC unit supply & installation", unit="no",
                    quantity=5, client_row_index=2, trade_category="mep"),
            BOQItem(project_id=project.id, package_id=package.id, line_number="2",
                    description="VRF outdoor condensing unit", unit="no",
                    quantity=2, client_row_index=3, trade_category="mep"),
        ])
        supplier = Supplier(name="CoolAir", emails=[], trade_categories=["mep"])
        seed.add(supplier)
        await seed.flush()
        offer = SupplierOffer(
            package_id=package.id, supplier_id=supplier.id,
            status=OfferStatus.SELECTED.value, file_paths=[], currency="USD",
            line_items=[
                {"description": "Supply and install split AC unit", "rate": 1200},
                {"description": "VRF outdoor condensing unit", "rate": 8000},
            ],
        )
        seed.add(offer)
        await seed.commit()
        ids = {"project": project.id, "package": package.id, "offer": offer.id}
        boq = (await seed.execute(select(BOQItem).order_by(BOQItem.id))).scalars().all()
        ids["item0"] = boq[0].id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, ids
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_populate_then_summary_and_gaps(pricing_client):
    client, ids = pricing_client
    async with client as c:
        pop = await c.post(f"/api/offers/{ids['offer']}/populate-prices")
        assert pop.status_code == 200, pop.text
        assert pop.json()["items_populated"] == 2

        summ = await c.get(f"/api/projects/{ids['project']}/pricing/summary")
        assert summ.status_code == 200
        assert summ.json()["cost_subtotal"] == 22000.0
        assert summ.json()["grand_total"] == round(22000.0 * 1.26, 2)

        gaps = await c.get(f"/api/projects/{ids['project']}/pricing/gaps")
        assert gaps.status_code == 200
        assert gaps.json()["unpriced_count"] == 0


async def test_populate_prices_404_missing_offer(pricing_client):
    client, ids = pricing_client
    async with client as c:
        r = await c.post("/api/offers/999999/populate-prices")
    assert r.status_code == 404


async def test_manual_price_override(pricing_client):
    client, ids = pricing_client
    async with client as c:
        r = await c.patch(f"/api/boq-items/{ids['item0']}/price",
                          json={"unit_rate": 1500, "notes": "negotiated"})
        assert r.status_code == 200
        assert r.json()["unit_rate"] == 1500
        assert r.json()["total_price"] == 7500  # qty 5
        assert (await c.patch("/api/boq-items/999999/price", json={"unit_rate": 1})).status_code == 404


async def test_populate_template_download_preserves_formulas(pricing_client):
    client, ids = pricing_client
    # build a client template whose rows 2/3 match the seeded client_row_index
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Item", "Description", "Unit", "Qty", "Rate", "Amount"])
    ws.append([1, "Split AC unit", "no", 5, None, "=D2*E2"])
    ws.append([2, "VRF unit", "no", 2, None, "=D3*E3"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    async with client as c:
        await c.post(f"/api/offers/{ids['offer']}/populate-prices")
        resp = await c.post(
            f"/api/projects/{ids['project']}/pricing/populate-template",
            files={"file": ("client.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    out = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws2 = out["BOQ"]
    assert ws2.cell(row=2, column=5).value == 1200.0  # rate written
    assert ws2.cell(row=2, column=6).value == "=D2*E2"  # formula preserved
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_pricing_api.py -q`
Expected: FAIL — router not registered / 404s.

- [ ] **Step 3: Implement the router**

Create `app/api/pricing.py`:

```python
"""Pricing API: populate BOQ from offers, summarize with markups, report gaps,
manual overrides, and formula-preserving client-template population."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.database import get_db
from app.models.boq import BOQItem
from app.models.project import Project
from app.schemas.pricing import (
    BOQItemPriceResponse,
    GapsReport,
    ItemPriceUpdate,
    PricePopulationResult,
    PricingSummary,
)
from app.services.pricing.pricing_service import PricingService
from app.services.pricing.template_writer import populate_template

router = APIRouter(tags=["pricing"])

# Cap inbound template uploads (consistent with app/api/suppliers.py and the
# Phase 9/10 fix — never read an unbounded body fully into memory).
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/offers/{offer_id}/populate-prices", response_model=PricePopulationResult)
async def populate_prices(
    offer_id: int,
    apply_markup: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> PricePopulationResult:
    try:
        result = await PricingService().populate_from_offer(
            db, offer_id, apply_markup=apply_markup
        )
    except ValueError as exc:
        # "not found" -> 404; business-rule violations -> 409
        msg = str(exc)
        status = 404 if "not found" in msg.lower() else 409
        raise HTTPException(status_code=status, detail=msg) from exc
    return PricePopulationResult(**result)


@router.get("/projects/{project_id}/pricing/summary", response_model=PricingSummary)
async def pricing_summary(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> PricingSummary:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return PricingSummary(**await PricingService().pricing_summary(db, project_id))


@router.get("/projects/{project_id}/pricing/gaps", response_model=GapsReport)
async def pricing_gaps(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> GapsReport:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return GapsReport(**await PricingService().gaps_report(db, project_id))


@router.patch("/boq-items/{item_id}/price", response_model=BOQItemPriceResponse)
async def update_item_price(
    item_id: int, payload: ItemPriceUpdate, db: AsyncSession = Depends(get_db)
) -> BOQItemPriceResponse:
    item = await PricingService().update_item_price(
        db, item_id, payload.unit_rate, notes=payload.notes
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"BOQ item {item_id} not found")
    return BOQItemPriceResponse.model_validate(item)


@router.post("/projects/{project_id}/pricing/populate-template")
async def populate_client_template(
    project_id: int,
    file: UploadFile = File(...),
    rate_column: int | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    rows = (
        await db.execute(
            select(BOQItem.client_row_index, BOQItem.unit_rate).where(
                BOQItem.project_id == project_id,
                BOQItem.unit_rate.is_not(None),
                BOQItem.client_row_index.is_not(None),
            )
        )
    ).all()
    row_rates = {int(idx): float(rate) for idx, rate in rows}
    if not row_rates:
        raise HTTPException(
            status_code=409,
            detail="No priced BOQ items with a client row mapping; populate prices first.",
        )

    suffix = Path(file.filename or "template.xlsx").suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as src_tmp:
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
        populate_template(src_path, out_path, row_rates, rate_column=rate_column)
    except ValueError as exc:
        Path(src_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _cleanup() -> None:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)

    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"priced_boq_project_{project_id}.xlsx",
        background=BackgroundTask(_cleanup),
    )
```

- [ ] **Step 4: Register the router in `app/main.py`**

Add the import (alphabetical block is fine):

```python
from app.api.pricing import router as pricing_router
```

Add the registration after the offers router:

```python
app.include_router(pricing_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/pricing/test_pricing_api.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/pricing.py app/main.py tests/pricing/test_pricing_api.py
git commit -m "feat(phase-11): pricing API — populate from offer, summary, gaps, manual override, template fill"
```

---

## Task 6: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, zero failures, no new skips. Baseline was 143; this phase adds 8 (matcher) + 9 (service) + 4 (template) + 4 (API) = **25** → roughly **168 passing** (±a couple). Hard requirement: zero failures.

- [ ] **Step 2: Smoke-check routes register**

Run:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'pricing' in p or 'populate-prices' in p or 'boq-items' in p))"
```
Expected to include:
```
/api/boq-items/{item_id}/price
/api/offers/{offer_id}/populate-prices
/api/projects/{project_id}/pricing/gaps
/api/projects/{project_id}/pricing/populate-template
/api/projects/{project_id}/pricing/summary
```

- [ ] **Step 3: Final commit (if anything uncommitted)**

```bash
git add -A
git commit -m "test(phase-11): full suite green — BOQ pricing + formula-preserving template"
```

---

## Spec Coverage Self-Review

| Phase 11 spec requirement (spec §6 cap 9) | Task |
|---|---|
| Price population from selected offers | 2, 5 |
| Fuzzy line-item mapping | 1, 2 |
| (Semantic mapping) | 1 (injectable `semantic_scorer` seam; deterministic fuzzy is the default — see note) |
| Markups | 3 |
| Gaps / risk report | 3, 5 |
| Formula-preserving client-template population | 4, 5 |
| Manual price override (works without LLM) | 3, 5 |
| Configurable market (markups/VAT/currency from rules) | 3 |
| Root conventions (`.value` enums, db param, no lazy load) | all |

**Scope note on "semantic" mapping:** the spec lists "fuzzy + semantic" mapping. This phase ships a strong deterministic fuzzy matcher (token-set Jaccard blended with difflib sequence ratio, handling reordered/partial descriptions) and exposes an injectable `semantic_scorer(a, b) -> float` seam on both `best_match` and `PricingService` for a future embedding-based blend. True embedding-based semantic matching is intentionally deferred (it would pull the multilingual sentence-transformer model into the hot path and tests); the seam means it can be added without changing the pricing contract. This is a deliberate, documented scope decision, not an omission.

**Deferred / out of scope:** indirects (Phase 12), historical-price benchmarking (Phase 13), client deliverables/dashboard (Phase 14), React UI (Phase 6C). Per-trade markup overrides (the salvage had a trade→markup map) are not implemented — markups are global from `rules.commercial.markup`; a per-trade override map can be added later without changing the summary contract.
