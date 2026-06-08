import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def pkg_client(tmp_path):
    from app.models import Base
    from app.models.project import Project
    from app.models.boq import BOQItem
    from app.database import get_db
    from app.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="P")
        seed.add(project)
        await seed.flush()
        for i, trade in enumerate(["concrete", "concrete", "mep"], start=1):
            seed.add(BOQItem(
                project_id=project.id, line_number=str(i), description=f"d{i}",
                unit="no", quantity=1, client_row_index=i, trade_category=trade,
            ))
        await seed.commit()
        project_id = project.id

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, project_id
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_generate_list_detail(pkg_client):
    client, pid = pkg_client
    async with client:
        gen = await client.post(f"/api/projects/{pid}/packages/generate")
        assert gen.status_code == 200, gen.text
        assert gen.json()["packages_created"] == 2

        lst = await client.get(f"/api/projects/{pid}/packages")
        assert lst.status_code == 200
        packages = lst.json()
        assert len(packages) == 2
        concrete = next(p for p in packages if p["trade_category"] == "concrete")
        assert concrete["total_items"] == 2

        detail = await client.get(f"/api/projects/{pid}/packages/{concrete['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["code"] == concrete["code"]
        assert len(body["items"]) == 2


async def test_generate_404_missing_project(pkg_client):
    client, _ = pkg_client
    async with client:
        r = await client.post("/api/projects/999999/packages/generate")
    assert r.status_code == 404


async def test_detail_404_missing_and_wrong_project(pkg_client):
    client, pid = pkg_client
    async with client:
        # generate so at least one real package exists for this project
        await client.post(f"/api/projects/{pid}/packages/generate")
        real_pkg = (await client.get(f"/api/projects/{pid}/packages")).json()[0]

        # missing package id -> 404
        missing = await client.get(f"/api/projects/{pid}/packages/999999")
        assert missing.status_code == 404

        # real package id but under a different (non-owning) project -> 404
        wrong = await client.get(f"/api/projects/424242/packages/{real_pkg['id']}")
    assert wrong.status_code == 404
