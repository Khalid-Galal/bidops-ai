async def test_user_and_org_roundtrip(db_session):
    from app.models.user import User, Organization
    org = Organization(name="Acme Contracting", code="ACME")
    db_session.add(org)
    await db_session.flush()
    user = User(
        email="est@acme.test", hashed_password="x", full_name="Est",
        role="estimator", organization_id=org.id,
    )
    db_session.add(user)
    await db_session.commit()
    from sqlalchemy import select
    got = (await db_session.execute(select(User))).scalar_one()
    assert got.email == "est@acme.test"
    assert got.role == "estimator"
