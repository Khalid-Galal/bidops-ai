async def test_email_log_roundtrip(db_session):
    from app.models.email import EmailLog
    log = EmailLog(
        email_type="rfq", status="draft",
        to=["sales@carrier.test"], subject="[P1]-PKG-1-RFQ", body_html="<p>hi</p>",
    )
    db_session.add(log)
    await db_session.commit()
    from sqlalchemy import select
    got = (await db_session.execute(select(EmailLog))).scalar_one()
    assert got.subject.endswith("RFQ")
    assert got.status == "draft"
