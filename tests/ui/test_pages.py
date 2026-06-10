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


async def test_workbench_has_rfq_and_offers_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert 'id="tab-rfq"' in r.text
        assert 'id="tab-offers"' in r.text


async def test_workbench_has_pricing_and_cost_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert 'id="tab-pricing"' in r.text
        assert 'id="tab-cost"' in r.text


async def test_workbench_has_historical_and_deliverables_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert 'id="tab-historical"' in r.text
        assert 'id="tab-deliverables"' in r.text


async def test_settings_page_renders(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/settings")
        assert r.status_code == 200
        assert "rules-json" in r.text
        assert 'href="/settings"' in r.text  # nav link present


async def test_suppliers_page_has_status_and_update_controls(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/suppliers")
        assert 'id="status-filter"' in r.text
        assert 'id="import-update"' in r.text


async def test_offers_tab_has_manual_entry_and_supplier_select(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert "editCommercial" in r.text          # manual no-LLM entry path
        assert 'id="offer-supplier"' in r.text     # supplier picker (no raw IDs)
        assert "offerDetail" in r.text             # compliance detail view
        assert 'id="rfq-lang"' in r.text           # RFQ language override
        assert "editEmail" in r.text               # draft edit before send


async def test_documents_table_renders_versioning(ui_client):
    from app.database import get_db
    from app.main import app as fastapi_app
    from app.models.document import Document

    client, pid = ui_client
    # Seed a superseded document with a reason that contains a double quote so we
    # can verify the title attribute is HTML-escaped.
    override = fastapi_app.dependency_overrides[get_db]
    agen = override()
    session = await agen.__anext__()
    session.add(Document(
        project_id=pid, filename="Mechanical_Spec_RevB.pdf", file_path="/m",
        file_type="pdf", file_size=1024, category="specs", version_label="rev B",
        is_superseded=True, supersede_reason='replaced by "rev C"',
    ))
    await session.commit()
    await agen.aclose()

    async with client as c:
        r = await c.get(f"/projects/{pid}")
    assert r.status_code == 200
    body = r.text
    assert "superseded" in body          # badge present
    assert "rev B" in body               # version label rendered
    # The quote in the reason must be HTML-escaped inside the title attribute.
    assert ("&quot;rev C&quot;" in body) or ("&#34;rev C&#34;" in body)
    assert 'title="replaced by "rev C""' not in body  # not a raw, broken attribute


async def test_project_page_has_versioning_controls(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}")
        assert "analyzeVersions" in r.text
        # the documents table renders Category/Version headers when docs exist;
        # with no docs the empty state shows — the button must exist regardless
        assert "Analyze versions" in r.text
