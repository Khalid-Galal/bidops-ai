import io

import httpx
import openpyxl
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def api_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_crud_and_list(api_client):
    async with api_client as c:
        created = await c.post("/api/suppliers", json={
            "name": "Acme", "emails": ["a@x.test"], "trade_categories": ["mep"]})
        assert created.status_code == 201, created.text
        sid = created.json()["id"]
        assert created.json()["code"] == "SUP-0001"

        got = await c.get(f"/api/suppliers/{sid}")
        assert got.status_code == 200 and got.json()["name"] == "Acme"

        patched = await c.patch(f"/api/suppliers/{sid}", json={"rating": 4.2})
        assert patched.json()["rating"] == 4.2

        lst = await c.get("/api/suppliers", params={"trade": "mep"})
        assert lst.status_code == 200 and len(lst.json()) == 1
        assert (await c.get("/api/suppliers", params={"trade": "concrete"})).json() == []

        assert (await c.get("/api/suppliers/999999")).status_code == 404


async def test_blacklist(api_client):
    async with api_client as c:
        sid = (await c.post("/api/suppliers", json={"name": "B", "emails": [], "trade_categories": []})).json()["id"]
        r = await c.post(f"/api/suppliers/{sid}/blacklist", json={"reason": "fraud"})
        assert r.status_code == 200 and r.json()["is_blacklisted"] is True
        # blacklisted => inactive => not in default list
        assert (await c.get("/api/suppliers")).json() == []


async def test_import_and_export(api_client):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Name", "Email", "Trade"]); ws.append(["Acme", "a@x.test", "MEP"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    async with api_client as c:
        up = await c.post(
            "/api/suppliers/import",
            files={"file": ("sup.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert up.status_code == 200, up.text
        assert up.json()["imported"] == 1

        exp = await c.get("/api/suppliers/export")
        assert exp.status_code == 200
        assert exp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert len(exp.content) > 0


async def test_import_malformed_returns_400(api_client):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Company", "Email"]); ws.append(["X", "x@x.test"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    async with api_client as c:
        up = await c.post(
            "/api/suppliers/import",
            files={"file": ("bad.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert up.status_code == 400, up.text
