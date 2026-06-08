async def test_harness_creates_tables(db_session):
    from sqlalchemy import text
    rows = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    names = {r[0] for r in rows}
    assert "projects" in names  # existing model proves create_all + registration work
