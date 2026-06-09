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
