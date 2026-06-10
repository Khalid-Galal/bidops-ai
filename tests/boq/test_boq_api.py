import io

import httpx
import pytest_asyncio
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _boq_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty"])
    ws.append(["1.1", "Reinforced concrete in raft", "cum", 6800])
    ws.append(["1.2", "Supply and install HVAC ductwork", "sqm", 31000])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest_asyncio.fixture
async def boq_client(tmp_path):
    """ASGI client whose get_db yields a fresh in-memory DB seeded with a project."""
    from app.models import Base
    from app.models.project import Project
    from app.database import get_db
    from app.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="P")
        seed.add(project)
        await seed.commit()
        project_id = project.id

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    yield client, project_id
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_parse_and_list_boq(boq_client):
    client, project_id = boq_client
    async with client:
        files = {"file": ("boq.xlsx", _boq_bytes(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = await client.post(f"/api/projects/{project_id}/boq/parse", files=files)
        assert r.status_code == 200, r.text
        summary = r.json()
        assert summary["total"] == 2
        assert summary["by_trade"].get("concrete") == 1
        assert summary["by_trade"].get("mep") == 1

        lst = await client.get(f"/api/projects/{project_id}/boq")
        assert lst.status_code == 200
        items = lst.json()
        assert len(items) == 2
        assert {i["trade_category"] for i in items} == {"concrete", "mep"}


async def test_boq_list_exposes_pricing_fields(boq_client):
    # Regression (Phase 6C review JSAPI-1): the workbench BOQ table renders
    # unit_rate/total_price — the response schema must not strip them.
    client, project_id = boq_client
    async with client:
        files = {"file": ("boq.xlsx", _boq_bytes(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        await client.post(f"/api/projects/{project_id}/boq/parse", files=files)
        items = (await client.get(f"/api/projects/{project_id}/boq")).json()
        item_id = items[0]["id"]
        # all pricing keys present (null before pricing)
        for key in ("unit_rate", "total_price", "currency", "mapping_confidence"):
            assert key in items[0]
        assert items[0]["unit_rate"] is None

        # set a manual rate, then the list must show it
        patched = await client.patch(f"/api/boq-items/{item_id}/price",
                                     json={"unit_rate": 123.5})
        assert patched.status_code == 200
        items2 = (await client.get(f"/api/projects/{project_id}/boq")).json()
        priced = next(i for i in items2 if i["id"] == item_id)
        assert priced["unit_rate"] == 123.5
        assert priced["total_price"] == round(123.5 * priced["quantity"], 2)
