from datetime import datetime, timezone

from sqlalchemy import select

from app.models.historical import HistoricalPrice


async def test_historical_price_persists(db_session):
    rec = HistoricalPrice(
        description="Supply and install split AC unit",
        unit="no", rate=1200.0, currency="USD", trade_category="mep",
        source="import:rates2025.xlsx", recorded_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)
    assert rec.id is not None
    assert rec.created_at is not None  # TimestampMixin
    got = (await db_session.execute(
        select(HistoricalPrice).where(HistoricalPrice.trade_category == "mep")
    )).scalar_one()
    assert got.rate == 1200.0
    assert got.source_project_id is None  # nullable
