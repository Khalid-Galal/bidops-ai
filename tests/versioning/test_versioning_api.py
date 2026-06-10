import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def ver_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.document import Document
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
            Document(project_id=project.id, filename="Spec_RevA.pdf", file_path="/m",
                     file_type="pdf", file_size=1, extracted_text="specification a"),
            Document(project_id=project.id, filename="Spec_RevB.pdf", file_path="/m",
                     file_type="pdf", file_size=1, extracted_text="specification b"),
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


async def test_analyze_endpoint(ver_client):
    client, pid = ver_client
    async with client as c:
        r = await c.post(f"/api/projects/{pid}/documents/analyze")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["superseded"] == 1
        assert body["by_category"]["specs"] == 2

        docs = (await c.get(f"/api/projects/{pid}/documents")).json()
        rev_a = next(d for d in docs if d["filename"] == "Spec_RevA.pdf")
        assert rev_a["is_superseded"] is True
        assert rev_a["category"] == "specs"
        assert rev_a["version_label"] == "rev A"


async def test_analyze_404_missing_project(ver_client):
    client, _ = ver_client
    async with client as c:
        r = await c.post("/api/projects/999999/documents/analyze")
    assert r.status_code == 404


async def test_supersede_rejects_self(ver_client):
    client, pid = ver_client
    async with client as c:
        docs = (await c.get(f"/api/projects/{pid}/documents")).json()
        target = docs[0]["id"]
        r = await c.patch(f"/api/documents/{target}/supersede",
                          json={"superseded_by_id": target})
    assert r.status_code == 422


async def test_supersede_rejects_cross_project(ver_client):
    from app.database import get_db
    from app.main import app as fastapi_app
    from app.models.document import Document
    from app.models.project import Project

    client, pid = ver_client
    # Create a document in a DIFFERENT project via the same overridden session.
    override = fastapi_app.dependency_overrides[get_db]
    agen = override()
    session = await agen.__anext__()
    other_project = Project(name="Other")
    session.add(other_project)
    await session.flush()
    other_doc = Document(project_id=other_project.id, filename="Foreign.pdf",
                         file_path="/m", file_type="pdf", file_size=1)
    session.add(other_doc)
    await session.commit()
    other_doc_id = other_doc.id
    await agen.aclose()

    async with client as c:
        docs = (await c.get(f"/api/projects/{pid}/documents")).json()
        target = docs[0]["id"]
        r = await c.patch(f"/api/documents/{target}/supersede",
                          json={"superseded_by_id": other_doc_id})
    assert r.status_code == 422


async def test_manual_supersede_and_undo(ver_client):
    client, pid = ver_client
    async with client as c:
        docs = (await c.get(f"/api/projects/{pid}/documents")).json()
        target = docs[0]["id"]
        r = await c.patch(f"/api/documents/{target}/supersede",
                          json={"reason": "replaced by addendum (manual)"})
        assert r.status_code == 200
        assert r.json()["is_superseded"] is True

        undo = await c.patch(f"/api/documents/{target}/supersede", json={"undo": True})
        assert undo.status_code == 200
        assert undo.json()["is_superseded"] is False

        assert (await c.patch("/api/documents/999999/supersede", json={})).status_code == 404
