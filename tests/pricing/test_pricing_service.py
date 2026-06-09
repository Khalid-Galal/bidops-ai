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
