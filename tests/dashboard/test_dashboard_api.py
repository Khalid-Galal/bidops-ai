import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def dash_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro Dashboard")
        seed.add(project)
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


async def test_dashboard_endpoint(dash_client):
    client, pid = dash_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["project"]["name"] == "Metro Dashboard"
        assert body["documents"]["total"] == 0
        assert body["packages"] == []


async def test_dashboard_404(dash_client):
    client, _ = dash_client
    async with client as c:
        r = await c.get("/api/projects/999999/dashboard")
    assert r.status_code == 404
