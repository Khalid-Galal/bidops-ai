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


async def test_link_documents_and_detail_shows_links(pkg_client, monkeypatch):
    from dataclasses import dataclass

    import app.api.packaging as pkg_api

    client, pid = pkg_client

    @dataclass
    class FakeHit:
        document_id: int
        score: float
        text: str
        page_number: int = 1
        filename: str = "spec.pdf"

    class FakeSearch:
        def __init__(self, hits):
            self._hits = hits

        def search(self, project_id, query, top_k=10, mode="hybrid"):
            return self._hits

    # Seed a real Document via the same DB the API uses: drive the override
    # dependency's async generator directly (app.main.app holds the override
    # object the fixture installed).
    from app.database import get_db
    from app.main import app as fastapi_app
    from app.models.document import Document

    override = fastapi_app.dependency_overrides[get_db]
    agen = override()
    session = await agen.__anext__()
    doc = Document(
        project_id=pid,
        filename="concrete_spec.pdf",
        file_path="/tmp/concrete_spec.pdf",
        file_type="pdf",
        file_size=1,
    )
    session.add(doc)
    await session.commit()
    doc_id = doc.id
    await agen.aclose()

    from app.services.packaging.document_linker import DocumentLinker

    # Force the linker to use a fake search returning a hit for that document.
    monkeypatch.setattr(
        pkg_api,
        "DocumentLinker",
        lambda: DocumentLinker(
            search_service=FakeSearch([FakeHit(doc_id, 0.88, "Concrete C35/45 spec", 7)])
        ),
    )

    async with client:
        await client.post(f"/api/projects/{pid}/packages/generate")
        link = await client.post(f"/api/projects/{pid}/packages/link-documents")
        assert link.status_code == 200, link.text
        assert link.json()["links_created"] >= 1

        packages = (await client.get(f"/api/projects/{pid}/packages")).json()
        concrete = next(p for p in packages if p["trade_category"] == "concrete")
        detail = (await client.get(f"/api/projects/{pid}/packages/{concrete['id']}")).json()
        assert any(ld["document_id"] == doc_id for ld in detail["linked_documents"])
        assert detail["linked_documents"][0]["filename"] == "concrete_spec.pdf"


async def test_export_and_register_download(pkg_client, monkeypatch, tmp_path):
    import app.api.packaging as pkg_api
    from app.services.packaging.package_exporter import PackageExporter

    client, pid = pkg_client

    # Force the exporter to write under a temp root (not data/packages).
    monkeypatch.setattr(
        pkg_api, "PackageExporter",
        lambda: PackageExporter(output_root=tmp_path / "pkgout"),
    )

    async with client:
        await client.post(f"/api/projects/{pid}/packages/generate")
        exp = await client.post(f"/api/projects/{pid}/packages/export")
        assert exp.status_code == 200, exp.text
        assert exp.json()["packages_exported"] == 2

        reg = await client.get(f"/api/projects/{pid}/packages/register")
        assert reg.status_code == 200
        assert reg.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(reg.content) > 0


async def test_register_download_404_before_export(pkg_client, monkeypatch, tmp_path):
    import app.api.packaging as pkg_api
    from app.services.packaging.package_exporter import PackageExporter

    client, pid = pkg_client
    monkeypatch.setattr(
        pkg_api, "PackageExporter",
        lambda: PackageExporter(output_root=tmp_path / "empty"),
    )
    async with client:
        r = await client.get(f"/api/projects/{pid}/packages/register")
    assert r.status_code == 404
