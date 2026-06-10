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
    yield client, pid, factory
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_dashboard_endpoint(dash_client):
    client, pid, _ = dash_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["project"]["name"] == "Metro Dashboard"
        assert body["documents"]["total"] == 0
        assert body["packages"] == []


async def test_dashboard_404(dash_client):
    client, _, _ = dash_client
    async with client as c:
        r = await c.get("/api/projects/999999/dashboard")
    assert r.status_code == 404


async def test_dashboard_populated(dash_client):
    from app.models.boq import BOQItem
    from app.models.document import Document
    from app.models.package import Package

    client, pid, factory = dash_client
    async with factory() as seed:
        seed.add(Document(project_id=pid, filename="specs.pdf",
                          file_path="docs/specs.pdf", file_type="pdf",
                          file_size=1234, status="completed"))
        package = Package(project_id=pid, name="HVAC", code="PKG-001-MEP",
                          trade_category="mep")
        seed.add(package)
        await seed.flush()
        seed.add(BOQItem(project_id=pid, package_id=package.id, line_number="1",
                         description="AC", unit="no", quantity=5, client_row_index=2,
                         trade_category="mep", unit_rate=1200, total_price=6000,
                         currency="USD"))
        await seed.commit()

    async with client as c:
        r = await c.get(f"/api/projects/{pid}/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["documents"]["total"] == 1
        assert body["boq"]["total"] == 1
        assert body["boq"]["priced"] == 1
        assert body["packages"][0]["code"] == "PKG-001-MEP"
        assert body["pricing"]["cost_subtotal"] > 0

        page = await c.get(f"/projects/{pid}/dashboard")
        assert page.status_code == 200
        assert "PKG-001-MEP" in page.text
