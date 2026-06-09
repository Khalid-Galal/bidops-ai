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
