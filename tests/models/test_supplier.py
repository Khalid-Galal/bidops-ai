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
