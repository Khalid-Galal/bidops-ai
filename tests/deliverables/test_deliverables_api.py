import io
import zipfile

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def deliv_client(tmp_path, monkeypatch):
    import app.api.deliverables as deliv_api
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.boq import BOQItem
    from app.models.project import Project
    from app.services.deliverables.deliverables_service import DeliverablesService

    monkeypatch.setattr(
        deliv_api, "DeliverablesService",
        lambda: DeliverablesService(output_root=tmp_path / "deliv"),
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        seed.add(BOQItem(project_id=project.id, line_number="1", description="AC",
                         unit="no", quantity=5, client_row_index=2, trade_category="mep",
                         unit_rate=1200, total_price=6000, currency="USD"))
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


async def test_build_then_download_zip(deliv_client):
    client, pid = deliv_client
    async with client as c:
        b = await c.post(f"/api/projects/{pid}/deliverables/build")
        assert b.status_code == 200, b.text
        assert "Pricing_Summary.xlsx" in b.json()["files"]

        d = await c.get(f"/api/projects/{pid}/deliverables/download")
        assert d.status_code == 200
        assert d.headers["content-type"].startswith("application/zip")
        zf = zipfile.ZipFile(io.BytesIO(d.content))
        assert any(n.endswith("Pricing_Summary.xlsx") for n in zf.namelist())
        assert any(n.endswith("manifest.json") for n in zf.namelist())


async def test_download_404_before_build(deliv_client):
    client, pid = deliv_client
    async with client as c:
        r = await c.get(f"/api/projects/{pid}/deliverables/download")
    assert r.status_code == 404


async def test_build_404_missing_project(deliv_client):
    client, _ = deliv_client
    async with client as c:
        r = await c.post("/api/projects/999999/deliverables/build")
    assert r.status_code == 404
