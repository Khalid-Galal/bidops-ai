import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def ui_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro UI")
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


async def test_suppliers_page_renders(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/suppliers")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Suppliers" in r.text
        assert "supplier-add-form" in r.text


async def test_base_nav_has_suppliers_link(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/")
        assert 'href="/suppliers"' in r.text


async def test_project_page_links_to_workbench(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}")
        assert f'href="/projects/{pid}/workbench"' in r.text
        assert f'href="/projects/{pid}/dashboard"' in r.text


async def test_workbench_renders_with_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert r.status_code == 200
        assert "Metro UI" in r.text
        assert 'id="tab-boq"' in r.text
        assert 'id="tab-packages"' in r.text


async def test_workbench_404_missing_project(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/projects/999999/workbench")
    assert r.status_code == 404
