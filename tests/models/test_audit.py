async def test_audit_log_roundtrip(db_session):
    from app.models.audit import AuditLog
    entry = AuditLog(
        action="extraction.run", entity_type="project", entity_id="1",
        description="ran summary extraction", success=True,
    )
    db_session.add(entry)
    await db_session.commit()
    from sqlalchemy import select
    got = (await db_session.execute(select(AuditLog))).scalar_one()
    assert got.action == "extraction.run"
    assert got.success is True
