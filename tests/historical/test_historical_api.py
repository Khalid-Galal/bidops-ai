import io

import httpx
import openpyxl
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def hist_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.boq import BOQItem
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Current")
        seed.add(project)
        await seed.flush()
        seed.add(BOQItem(project_id=project.id, line_number="1",
                         description="Split AC unit supply and install", unit="no",
                         quantity=5, client_row_index=2, trade_category="mep"))
        await seed.commit()
        pid = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, pid
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_add_list_and_suggest(hist_client):
    client, _ = hist_client
    async with client as c:
        a = await c.post("/api/historical", json={
            "description": "Supply and install split AC unit", "rate": 1200,
            "unit": "no", "currency": "USD", "trade_category": "mep"})
        assert a.status_code == 201, a.text
        await c.post("/api/historical", json={
            "description": "Split AC unit supply & installation", "rate": 1300,
            "trade_category": "mep", "currency": "USD"})

        lst = await c.get("/api/historical", params={"trade": "mep"})
        assert lst.status_code == 200 and len(lst.json()) == 2

        sug = await c.get("/api/historical/suggest",
                          params={"description": "Split AC unit (supply & install)", "trade": "mep"})
        assert sug.status_code == 200
        assert sug.json()["benchmark"]["suggested_rate"] == 1250.0


async def test_import_endpoint(hist_client):
    client, _ = hist_client
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Description", "Unit", "Rate", "Trade", "Currency"])
    ws.append(["Concrete C30", "m3", 90, "Civil", "USD"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    async with client as c:
        r = await c.post("/api/historical/import",
                         files={"file": ("rates.xlsx", buf.getvalue(),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 200, r.text
        assert r.json()["imported"] == 1


async def test_import_rejects_non_xlsx(hist_client):
    client, _ = hist_client
    async with client as c:
        r = await c.post("/api/historical/import",
                         files={"file": ("x.txt", b"not a spreadsheet", "text/plain")})
    assert r.status_code == 400


async def test_feedback_then_suggest(hist_client):
    client, _ = hist_client
    async with client as c:
        fb = await c.post("/api/historical/feedback", json={
            "description": "Split AC unit", "accepted_rate": 1275, "trade_category": "mep"})
        assert fb.status_code == 201
        sug = await c.get("/api/historical/suggest",
                          params={"description": "Split AC unit", "trade": "mep"})
        assert sug.json()["benchmark"]["suggested_rate"] == 1275.0


async def test_index_then_project_suggestions(hist_client):
    client, pid = hist_client
    # Index a SEPARATE past project so the current project gets a suggestion.
    async with client as c:
        # seed a past project with a priced item via the add endpoint (corpus directly)
        await c.post("/api/historical", json={
            "description": "Split AC unit supply and install", "rate": 1200,
            "trade_category": "mep", "currency": "USD"})
        sugg = await c.get(f"/api/projects/{pid}/historical/suggestions",
                           params={"only_unpriced": True})
        assert sugg.status_code == 200
        body = sugg.json()
        assert body["project_id"] == pid
        assert len(body["suggestions"]) == 1
        assert body["suggestions"][0]["suggestion"]["benchmark"]["suggested_rate"] == 1200.0

        idx = await c.post(f"/api/projects/{pid}/historical/index")
        assert idx.status_code == 200
        assert idx.json()["indexed"] == 0  # current project has no priced items


async def test_suggestions_404_missing_project(hist_client):
    client, _ = hist_client
    async with client as c:
        r = await c.get("/api/projects/999999/historical/suggestions")
    assert r.status_code == 404
