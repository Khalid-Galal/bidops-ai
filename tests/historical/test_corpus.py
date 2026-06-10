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


async def test_trade_filter_normalizes_casing(db_session, tmp_path):
    svc = HistoricalService()
    # One row added via add() with a differently-cased trade ("MEP" -> "mep").
    await svc.add(db_session, description="Split AC unit", rate=1200.0,
                  unit="no", currency="USD", trade_category="MEP")
    # One row imported as the canonical "mep" token.
    f = _make_rate_sheet(tmp_path / "mep.xlsx", [
        ("Split AC unit", "no", 1300, "mep", "USD"),
    ])
    await svc.import_excel(db_session, f)
    # A single suggest with the canonical token aggregates BOTH rows
    # (they share the canonical "mep" key after normalization).
    out = await svc.suggest(db_session, "Split AC unit", trade="mep")
    assert out["benchmark"]["count"] == 2

    # A spaced/cased trade label round-trips: importing "MEP Works" and
    # querying "MEP Works" both normalize to "mep_works" and match.
    g = _make_rate_sheet(tmp_path / "mepworks.xlsx", [
        ("Cable tray 200mm", "m", 25, "MEP Works", "USD"),
    ])
    await svc.import_excel(db_session, g)
    out2 = await svc.suggest(db_session, "Cable tray 200mm", trade="MEP Works")
    assert out2["benchmark"]["count"] >= 1


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


async def test_suggest_for_project_excludes_own_items(db_session):
    # Project A (the corpus source) and Project B (the one we suggest for).
    proj_a = Project(name="Past Tender")
    proj_b = Project(name="Current Tender")
    db_session.add_all([proj_a, proj_b])
    await db_session.flush()
    # Corpus: a record sourced from project A.
    db_session.add(HistoricalPrice(
        description="Supply and install split AC unit", unit="no", rate=1200.0,
        currency="USD", trade_category="mep", source="project:Past Tender",
        source_project_id=proj_a.id,
    ))
    # A record sourced from project B itself (must be excluded from B's suggestions).
    db_session.add(HistoricalPrice(
        description="Split AC unit supply and installation", unit="no", rate=9999.0,
        currency="USD", trade_category="mep", source="project:Current Tender",
        source_project_id=proj_b.id,
    ))
    # Unpriced item in project B that we want a suggestion for.
    db_session.add(BOQItem(
        project_id=proj_b.id, line_number="1", description="Split AC unit (supply & install)",
        unit="no", quantity=5, client_row_index=2, trade_category="mep",
    ))
    await db_session.commit()

    out = await HistoricalService().suggest_for_project(db_session, proj_b.id)
    assert len(out["suggestions"]) == 1
    sugg = out["suggestions"][0]["suggestion"]
    # only project A's 1200 is in scope; B's own 9999 is excluded
    assert sugg["benchmark"]["suggested_rate"] == 1200.0
    assert all(m["source_project_id"] != proj_b.id for m in sugg["matches"])


async def test_suggest_for_project_only_unpriced(db_session):
    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    db_session.add_all([
        BOQItem(project_id=project.id, line_number="1", description="Priced item",
                unit="no", quantity=1, client_row_index=2, trade_category="mep",
                unit_rate=500, total_price=500),
        BOQItem(project_id=project.id, line_number="2", description="Unpriced item",
                unit="no", quantity=1, client_row_index=3, trade_category="mep"),
    ])
    await db_session.commit()
    out = await HistoricalService().suggest_for_project(db_session, project.id, only_unpriced=True)
    assert len(out["suggestions"]) == 1
    assert out["suggestions"][0]["description"] == "Unpriced item"
