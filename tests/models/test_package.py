async def test_package_roundtrip(db_session):
    from app.models.package import Package, PackageDocument
    from app.models.project import Project

    project = Project(name="P1")
    db_session.add(project)
    await db_session.flush()

    pkg = Package(
        project_id=project.id,
        code="PKG-P1-CONC-001",
        name="Concrete Works",
        trade_category="concrete",
        status="draft",
    )
    db_session.add(pkg)
    await db_session.commit()

    from sqlalchemy import select
    got = (await db_session.execute(select(Package))).scalar_one()
    assert got.code == "PKG-P1-CONC-001"
    assert got.project_id == project.id
