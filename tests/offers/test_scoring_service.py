import pytest

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.schemas.rules import RulesConfig
from app.services.offer.scoring_service import ScoringService


class _FakeRules:
    """Stands in for RulesService — returns a fixed RulesConfig from load()."""

    def __init__(self, cfg):
        self._cfg = cfg

    def load(self):
        return self._cfg


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
    # overall strictly descending
    overalls = [r["overall_score"] for r in ranking]
    assert overalls == sorted(overalls, reverse=True)


async def test_band_exact_mapping(db_session):
    package, offers = await _seed_offers(db_session)
    # Add a worst-on-every-axis offer to exercise the unacceptable fallthrough:
    # most expensive, slowest, zero technical.
    worst = SupplierOffer(
        package_id=package.id, supplier_id=offers[0].supplier_id,
        status=OfferStatus.RECEIVED.value, file_paths=[],
        total_price=1000.0, currency="USD", delivery_weeks=52, technical_score=0,
    )
    db_session.add(worst)
    await db_session.commit()
    await db_session.refresh(worst)
    result = await ScoringService().score_package(db_session, package.id)
    by_id = {r["offer_id"]: r for r in result["ranking"]}
    top = result["ranking"][0]
    # top offer: overall 75.0 == default 'good' threshold (exact mapping).
    assert top["overall_score"] == 75.0
    assert top["band"] == "good"
    # worst offer falls below the 'poor' threshold -> unacceptable.
    assert by_id[worst.id]["band"] == "unacceptable"


async def test_nondefault_weights_normalized(db_session):
    package, offers = await _seed_offers(db_session)
    cfg = RulesConfig()
    # All five weights equal and summing to >1 (5 * 1.0). overall must equal the
    # plain average of the five sub-scores, proving division by the true wsum.
    for field in type(cfg.scoring.weights).model_fields:
        setattr(cfg.scoring.weights, field, 1.0)
    result = await ScoringService(rules_service=_FakeRules(cfg)).score_package(
        db_session, package.id
    )
    for row in result["ranking"]:
        sub = row["subscores"]
        expected = round(sum(sub.values()) / len(sub), 1)
        assert row["overall_score"] == expected


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


async def test_payment_terms_scored_from_net_days(db_session):
    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    package = Package(project_id=project.id, name="X", code="C", trade_category="mep")
    db_session.add(package)
    supplier = Supplier(name="S", emails=[], trade_categories=["mep"])
    db_session.add(supplier)
    await db_session.flush()
    o30 = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                        status=OfferStatus.RECEIVED.value, file_paths=[],
                        total_price=100.0, delivery_weeks=4, payment_terms="Net 30")
    o60 = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                        status=OfferStatus.RECEIVED.value, file_paths=[],
                        total_price=100.0, delivery_weeks=4, payment_terms="Net 60")
    db_session.add_all([o30, o60])
    await db_session.commit()
    await db_session.refresh(o30)
    await db_session.refresh(o60)
    result = await ScoringService().score_package(db_session, package.id)
    by_id = {r["offer_id"]: r for r in result["ranking"]}
    # longer net-days favors the buyer -> Net 60 is best (100), Net 30 is half.
    assert by_id[o60.id]["subscores"]["payment_terms"] == 100.0
    assert by_id[o30.id]["subscores"]["payment_terms"] == 50.0


async def test_compare_currency_fallback_to_rules_default(db_session):
    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    package = Package(project_id=project.id, name="X", code="C", trade_category="mep")
    db_session.add(package)
    supplier = Supplier(name="S", emails=[], trade_categories=["mep"])
    db_session.add(supplier)
    await db_session.flush()
    # Offer carries no currency -> compare() falls back to rules.commercial.currency.
    o = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.RECEIVED.value, file_paths=[], total_price=100.0)
    db_session.add(o)
    await db_session.commit()
    cfg = RulesConfig()
    cfg.commercial.currency = "EGP"
    result = await ScoringService(rules_service=_FakeRules(cfg)).compare(
        db_session, package.id
    )
    assert result["currency"] == "EGP"


async def test_compare_offer_currency_wins_over_rules_default(db_session):
    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    package = Package(project_id=project.id, name="X", code="C", trade_category="mep")
    db_session.add(package)
    supplier = Supplier(name="S", emails=[], trade_categories=["mep"])
    db_session.add(supplier)
    await db_session.flush()
    o = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.RECEIVED.value, file_paths=[],
                      total_price=100.0, currency="GBP")
    db_session.add(o)
    await db_session.commit()
    cfg = RulesConfig()
    cfg.commercial.currency = "EGP"
    result = await ScoringService(rules_service=_FakeRules(cfg)).compare(
        db_session, package.id
    )
    # An offer's own currency takes precedence over the rules default.
    assert result["currency"] == "GBP"


