import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def indirects_client():
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
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        seed.add_all([
            BOQItem(project_id=project.id, line_number="1", description="AC",
                    unit="no", quantity=5, client_row_index=2, trade_category="mep",
                    unit_rate=1200, total_price=6000, currency="USD"),
            BOQItem(project_id=project.id, line_number="2", description="VRF",
                    unit="no", quantity=2, client_row_index=3, trade_category="mep",
                    unit_rate=8000, total_price=16000, currency="USD"),
        ])
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


async def test_indirects_endpoint(indirects_client):
    client, pid = indirects_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/indirects")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["direct_cost"] == 22000.0
        assert body["indirects"]["total_indirects"] == 1870.0
        assert body["indirects"]["location"] == "default"


async def test_cost_summary_endpoint(indirects_client):
    client, pid = indirects_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/cost-summary", params={"duration_months": 0})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_cost_base"] == 23870.0
        assert body["grand_total"] == round(23870.0 * 1.26, 2)


async def test_indirects_404_missing_project(indirects_client):
    client, _ = indirects_client
    async with client as c:
        r = await c.get("/api/projects/999999/indirects")
    assert r.status_code == 404


async def test_cost_summary_unknown_location_falls_back(indirects_client):
    client, pid = indirects_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/cost-summary", params={"location": "atlantis"})
        assert r.status_code == 200
        assert r.json()["indirects"]["location_factor"] == 1.0
