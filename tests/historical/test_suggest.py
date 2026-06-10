import pytest

from app.models.historical import HistoricalPrice
from app.services.historical.historical_service import HistoricalService


async def _seed_corpus(db):
    db.add_all([
        HistoricalPrice(description="Supply and install split AC unit", unit="no",
                        rate=1200.0, currency="USD", trade_category="mep", source="import:a"),
        HistoricalPrice(description="Split AC unit supply & installation", unit="no",
                        rate=1300.0, currency="USD", trade_category="mep", source="import:a"),
        HistoricalPrice(description="VRF outdoor condensing unit", unit="no",
                        rate=8000.0, currency="USD", trade_category="mep", source="import:a"),
        HistoricalPrice(description="Concrete grade C30 foundation", unit="m3",
                        rate=90.0, currency="USD", trade_category="civil", source="import:a"),
    ])
    await db.commit()


async def test_add_record(db_session):
    svc = HistoricalService()
    rec = await svc.add(db_session, description="Steel rebar", rate=750.0, trade_category="concrete")
    assert rec.id is not None
    assert rec.source == "manual"  # default source


async def test_suggest_aggregates_similar_rates(db_session):
    await _seed_corpus(db_session)
    out = await HistoricalService().suggest(
        db_session, "Split AC unit (supply & install)", trade="mep"
    )
    # the two AC records match; VRF is too different
    assert out["benchmark"]["count"] == 2
    assert out["benchmark"]["min"] == 1200.0
    assert out["benchmark"]["max"] == 1300.0
    assert out["benchmark"]["median"] == 1250.0
    assert out["benchmark"]["suggested_rate"] == 1250.0  # median
    assert out["benchmark"]["currency"] == "USD"
    descs = {m["description"] for m in out["matches"]}
    assert "VRF outdoor condensing unit" not in descs
    # every match carries traceability (id + similarity)
    assert all("historical_id" in m and m["similarity"] >= 0.45 for m in out["matches"])


async def test_suggest_trade_filter_excludes_other_trades(db_session):
    await _seed_corpus(db_session)
    out = await HistoricalService().suggest(db_session, "Concrete grade C30 foundation", trade="civil")
    assert out["benchmark"]["count"] == 1
    assert out["benchmark"]["suggested_rate"] == 90.0


async def test_suggest_no_match_returns_empty_benchmark(db_session):
    await _seed_corpus(db_session)
    out = await HistoricalService().suggest(db_session, "Curtain wall structural glazing", trade="mep")
    assert out["benchmark"]["count"] == 0
    assert out["benchmark"]["suggested_rate"] is None
    assert out["matches"] == []


async def test_suggest_respects_top_k(db_session):
    db_session.add_all([
        HistoricalPrice(description="cable tray 100mm", rate=float(10 + i),
                        trade_category="mep", source="import:b")
        for i in range(8)
    ])
    await db_session.commit()
    out = await HistoricalService().suggest(db_session, "cable tray 100mm", trade="mep", top_k=3)
    assert len(out["matches"]) == 3
    assert out["benchmark"]["count"] == 3
    # Deterministic tie-break: all 8 rows tie on similarity, so the first three
    # by id survive -> rates 10.0, 11.0, 12.0 (median 11.0), every run.
    assert [m["rate"] for m in out["matches"]] == [10.0, 11.0, 12.0]
    assert out["benchmark"]["median"] == 11.0


async def test_benchmark_uses_dominant_currency(db_session):
    db_session.add_all([
        HistoricalPrice(description="Supply and install split AC unit", unit="no",
                        rate=1200.0, currency="USD", trade_category="mep", source="import:c"),
        HistoricalPrice(description="Supply and install split AC unit", unit="no",
                        rate=1300.0, currency="USD", trade_category="mep", source="import:c"),
        HistoricalPrice(description="Supply and install split AC unit", unit="no",
                        rate=40000.0, currency="EGP", trade_category="mep", source="import:c"),
    ])
    await db_session.commit()
    out = await HistoricalService().suggest(
        db_session, "Supply and install split AC unit", trade="mep"
    )
    # Benchmark covers only the dominant (USD) bucket; the EGP outlier is excluded.
    assert out["benchmark"]["currency"] == "USD"
    assert out["benchmark"]["count"] == 2
    assert out["benchmark"]["suggested_rate"] == 1250.0
    # ...but every candidate still shows up in matches for full traceability.
    assert len(out["matches"]) == 3


async def test_unit_mismatch_demotes(db_session):
    db_session.add_all([
        HistoricalPrice(description="excavation works", unit="m3", rate=50.0,
                        trade_category="civil", source="import:d"),
        HistoricalPrice(description="excavation works", unit="no", rate=5.0,
                        trade_category="civil", source="import:d"),
    ])
    await db_session.commit()
    svc = HistoricalService()
    # The unit-matching row ranks first whichever unit the query asks for.
    out_m3 = await svc.suggest(db_session, "excavation works", unit="m3")
    assert out_m3["matches"][0]["unit"] == "m3"
    out_no = await svc.suggest(db_session, "excavation works", unit="no")
    assert out_no["matches"][0]["unit"] == "no"
