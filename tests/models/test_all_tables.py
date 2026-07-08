async def test_all_v2_tables_created(db_session):
    from sqlalchemy import text
    rows = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    names = {r[0] for r in rows}
    for expected in [
        "boq_items", "packages", "package_documents", "suppliers",
        "supplier_offers", "email_logs",
    ]:
        assert expected in names, f"missing table: {expected}"
