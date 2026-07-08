import pytest

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.pricing.pricing_service import PricingService


async def _seed_priced(db, *, offer_status=OfferStatus.SELECTED.value, line_items=None,
                       currency="USD"):
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
        file_paths=[], currency=currency,
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


async def test_populate_stores_raw_cost(db_session):
    package, offer, items = await _seed_priced(db_session)
    await PricingService().populate_from_offer(db_session, offer.id)
    await db_session.refresh(items[0])
    # raw cost rate is stored — no markup uplift at population time
    assert items[0].unit_rate == 1200
    assert items[0].total_price == 6000


async def test_populate_then_summary_applies_markup_once(db_session):
    package, offer, items = await _seed_priced(db_session)
    await PricingService().populate_from_offer(db_session, offer.id)
    summary = await PricingService().pricing_summary(db_session, package.project_id)
    # populate stored raw cost (22000); summary applies the 0.26 markup exactly
    # once -> NOT compounded (×1.26²).
    assert summary["grand_total"] == round(22000.0 * 1.26, 2)


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


async def test_excluded_item_not_in_summary(db_session):
    package, offer, items = await _seed_priced(db_session)
    await PricingService().populate_from_offer(db_session, offer.id)
    before = await PricingService().pricing_summary(db_session, package.project_id)
    # items[1] (VRF) is priced at 8000*2 = 16000; exclude it
    await db_session.refresh(items[1])
    excluded_total = items[1].total_price
    assert excluded_total == 16000
    items[1].is_excluded = True
    await db_session.commit()
    after = await PricingService().pricing_summary(db_session, package.project_id)
    expected_subtotal = round(before["cost_subtotal"] - excluded_total, 2)
    assert after["cost_subtotal"] == expected_subtotal
    # default vat_rate is 0.0, so grand_total == subtotal * 1.26
    assert after["grand_total"] == round(expected_subtotal * 1.26, 2)
    assert after["priced_items"] == before["priced_items"] - 1


async def test_pricing_summary_respects_rules_vat(db_session):
    from app.schemas.rules import RulesConfig

    class _FakeRules:
        def __init__(self):
            self._cfg = RulesConfig()
            self._cfg.commercial.vat_rate = 0.10
            self._cfg.commercial.currency = "EGP"

        def load(self):
            return self._cfg

    # Offer priced in EGP and rules' commercial currency also EGP -> the labeled
    # currency is consistent with the numbers (which carry no FX conversion).
    package, offer, items = await _seed_priced(db_session, currency="EGP")
    svc = PricingService(rules_service=_FakeRules())
    await svc.populate_from_offer(db_session, offer.id)
    summary = await svc.pricing_summary(db_session, package.project_id)
    selling = round(22000.0 * 1.26, 2)
    assert summary["vat_rate"] == 0.10
    assert summary["vat_amount"] == round(selling * 0.10, 2)
    assert summary["grand_total"] == round(selling * 1.10, 2)
    assert summary["currency"] == "EGP"


async def test_summary_currency_falls_back_when_no_priced_items(db_session):
    # No priced items at all -> currency must fall back to the rules currency
    # (default "USD") without crashing.
    project = Project(name="Empty")
    db_session.add(project)
    await db_session.commit()
    summary = await PricingService().pricing_summary(db_session, project.id)
    assert summary["currency"] == "USD"
    assert summary["priced_items"] == 0


async def test_zero_price_counts_as_priced(db_session):
    package, offer, items = await _seed_priced(db_session)
    svc = PricingService()
    # A deliberate zero price is a real price, not a gap. Only items[2] gets a
    # price (0.0); the other two stay unpriced.
    await svc.update_item_price(db_session, items[2].id, 0.0)
    await db_session.refresh(items[2])
    assert items[2].total_price == 0.0

    gaps = await svc.gaps_report(db_session, package.project_id)
    assert not any(g["id"] == items[2].id for g in gaps["unpriced"])

    summary = await svc.pricing_summary(db_session, package.project_id)
    # the zero-priced item is the only one counted among priced items
    assert summary["priced_items"] == 1


async def test_repopulate_clears_stale_price(db_session):
    package, offer, items = await _seed_priced(db_session)
    svc = PricingService()
    await svc.populate_from_offer(db_session, offer.id)
    await db_session.refresh(items[0])
    assert items[0].unit_rate == 1200  # priced from offer A

    # Mutate the offer so its line items no longer match items[0]'s description.
    offer.line_items = [
        {"description": "Completely unrelated plumbing fixture", "rate": 50},
    ]
    await db_session.commit()
    await svc.populate_from_offer(db_session, offer.id)
    await db_session.refresh(items[0])
    assert items[0].unit_rate is None
    assert items[0].total_price is None
    assert items[0].currency is None
    assert items[0].selected_offer_id is None

    gaps = await svc.gaps_report(db_session, package.project_id)
    assert any(g["id"] == items[0].id for g in gaps["unpriced"])


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


async def test_populate_flags_quantity_mismatch_beyond_tolerance(db_session):
    # items[0] has BOQ quantity 5; offer line item states quantity 2 -> 60%
    # deviation, well beyond the default 5% tolerance -> flagged for review
    # even though the description match itself is high-confidence.
    package, offer, items = await _seed_priced(
        db_session,
        line_items=[
            {"description": "Split AC unit supply & installation", "rate": 1200,
             "unit": "no", "quantity": 2},
        ],
    )
    result = await PricingService().populate_from_offer(db_session, offer.id)
    assert result["items_needs_review"] == 1
    await db_session.refresh(items[0])
    assert items[0].unit_rate == 1200  # still priced
    assert items[0].requires_review is True
    assert "quantity" in items[0].review_notes.lower()


async def test_populate_within_tolerance_not_flagged(db_session):
    # BOQ quantity 5, offer line item quantity 5.1 -> 2% deviation, within the
    # default 5% tolerance -> not flagged.
    package, offer, items = await _seed_priced(
        db_session,
        line_items=[
            {"description": "Split AC unit supply & installation", "rate": 1200,
             "unit": "no", "quantity": 5.1},
        ],
    )
    await PricingService().populate_from_offer(db_session, offer.id)
    await db_session.refresh(items[0])
    assert items[0].requires_review is False
    assert items[0].review_notes is None
