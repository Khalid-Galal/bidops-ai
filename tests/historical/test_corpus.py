import openpyxl
import pytest
from sqlalchemy import select

from app.models.boq import BOQItem
from app.models.historical import HistoricalPrice
from app.models.project import Project
from app.services.historical.historical_service import HistoricalService


def _make_rate_sheet(path, rows, headers=("Description", "Unit", "Rate", "Trade", "Currency")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return str(path)


async def test_import_excel_creates_records(db_session, tmp_path):
    f = _make_rate_sheet(tmp_path / "rates.xlsx", [
        ("Supply and install split AC unit", "no", 1200, "MEP", "USD"),
        ("Concrete grade C30", "m3", 90, "Civil", "USD"),
        ("", "no", 5, "MEP", "USD"),  # blank description -> skipped
        ("Missing rate", "no", "", "MEP", "USD"),  # no usable rate -> skipped
    ])
    svc = HistoricalService()
    res = await svc.import_excel(db_session, f)
    assert res["imported"] == 2
    assert res["skipped"] == 2
    recs = (await db_session.execute(select(HistoricalPrice))).scalars().all()
    assert {r.description for r in recs} == {"Supply and install split AC unit", "Concrete grade C30"}
    # trade normalized to a lowercase token (matches rules trade keys)
    assert {r.trade_category for r in recs} == {"mep", "civil"}
    assert all(r.source.startswith("import:") for r in recs)


async def test_index_project_snapshots_priced_items(db_session):
    project = Project(name="Metro Line 3")
    db_session.add(project)
    await db_session.flush()
    db_session.add_all([
        BOQItem(project_id=project.id, line_number="1", description="AC unit", unit="no",
                quantity=5, client_row_index=2, trade_category="mep",
                unit_rate=1200, total_price=6000, currency="USD"),
        BOQItem(project_id=project.id, line_number="2", description="Unpriced", unit="no",
                quantity=1, client_row_index=3, trade_category="mep"),  # no unit_rate -> skipped
        BOQItem(project_id=project.id, line_number="3", description="Excluded", unit="no",
                quantity=1, client_row_index=4, trade_category="mep",
                unit_rate=999, total_price=999, currency="USD", is_excluded=True),  # excluded
    ])
    await db_session.commit()
    svc = HistoricalService()
    res = await svc.index_project(db_session, project.id)
    assert res["indexed"] == 1  # only the one priced, non-excluded item
    rec = (await db_session.execute(
        select(HistoricalPrice).where(HistoricalPrice.source_project_id == project.id)
    )).scalar_one()
    assert rec.rate == 1200.0
    assert rec.source == "project:Metro Line 3"
    # re-indexing is idempotent (no duplicate rows)
    res2 = await svc.index_project(db_session, project.id)
    assert res2["indexed"] == 1
    count = len((await db_session.execute(
        select(HistoricalPrice).where(HistoricalPrice.source_project_id == project.id)
    )).scalars().all())
    assert count == 1


async def test_record_feedback_adds_corpus_record(db_session):
    svc = HistoricalService()
    rec = await svc.record_feedback(
        db_session, description="Split AC unit", accepted_rate=1275.0,
        unit="no", currency="USD", trade_category="mep",
    )
    assert rec.id is not None
    assert rec.rate == 1275.0
    assert rec.source == "feedback"
    # feedback immediately participates in suggestions
    out = await svc.suggest(db_session, "Split AC unit", trade="mep")
    assert out["benchmark"]["suggested_rate"] == 1275.0
