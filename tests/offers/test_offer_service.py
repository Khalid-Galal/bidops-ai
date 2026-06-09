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
