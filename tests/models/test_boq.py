async def test_boq_item_roundtrip(db_session):
    from app.models.boq import BOQItem
    from app.models.project import Project

    project = Project(name="P1")
    db_session.add(project)
    await db_session.flush()

    item = BOQItem(
        project_id=project.id,
        description="Reinforced concrete C35/45 in columns",
        unit="m3",
        quantity=5400,
        trade_category="concrete",
    )
    db_session.add(item)
    await db_session.commit()

    from sqlalchemy import select
    got = (await db_session.execute(select(BOQItem))).scalar_one()
    assert got.description.startswith("Reinforced concrete")
    assert got.unit == "m3"
    assert got.project_id == project.id
