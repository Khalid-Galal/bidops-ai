import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def documents_client(tmp_path, monkeypatch):
    # Save uploaded files under tmp, not the repo's data/ dir.
    monkeypatch.chdir(tmp_path)
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.project import Project

    # Avoid real background parsing (no network/LLM/model calls in tests).
    async def _noop_batch(task_id, project_id, file_records):
        return None

    monkeypatch.setattr("app.api.documents.process_documents_batch", _noop_batch)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.commit()
        project_id = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, project_id
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_upload_saves_file_with_sanitized_name(documents_client, tmp_path):
    client, project_id = documents_client
    async with client as c:
        resp = await c.post(
            f"/api/projects/{project_id}/upload",
            files={"files": ("../../evil.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["uploaded"] == 1
        assert body["filenames"] == ["../../evil.txt"]

        docs = await c.get(f"/api/projects/{project_id}/documents")
        assert docs.status_code == 200
        assert docs.json()[0]["filename"] == "../../evil.txt"

        # The saved file must stay inside the project's upload dir - no
        # traversal from the raw filename despite the "../../" prefix.
        upload_dir = tmp_path / "data" / "uploads" / str(project_id)
        saved = list(upload_dir.glob("*evil.txt"))
        assert len(saved) == 1
        assert saved[0].read_bytes() == b"hello world"


async def test_upload_oversized_returns_413(documents_client, monkeypatch):
    client, project_id = documents_client
    monkeypatch.setattr("app.api.documents._MAX_UPLOAD_BYTES", 10)
    async with client as c:
        resp = await c.post(
            f"/api/projects/{project_id}/upload",
            files={"files": ("big.txt", b"0123456789ABCDEF", "text/plain")},
        )
        assert resp.status_code == 413, resp.text
