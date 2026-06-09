import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def emails_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.package import Package
    from app.models.project import Project
    from app.models.supplier import Supplier

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                          trade_category="mep", description="HVAC scope")
        seed.add(package)
        seed.add(Supplier(name="CoolAir", emails=["s@coolair.test"],
                          trade_categories=["mep"], preferred_language="en"))
        await seed.commit()
        ids = {"project": project.id, "package": package.id}
        sup = (await seed.execute(
            __import__("sqlalchemy").select(Supplier))).scalars().first()
        ids["supplier"] = sup.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, ids
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_suggested_then_create_and_preview(emails_client):
    client, ids = emails_client
    async with client as c:
        sug = await c.get(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/suggested-suppliers")
        assert sug.status_code == 200
        assert any(s["id"] == ids["supplier"] for s in sug.json())

        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        assert rfq.status_code == 201, rfq.text
        body = rfq.json()
        assert body["drafts_created"] == 1
        email_id = body["email_ids"][0]

        preview = await c.get(f"/api/emails/{email_id}")
        assert preview.status_code == 200
        assert preview.json()["status"] == "draft"
        assert preview.json()["subject"] == "[Metro] RFQ - HVAC"

        log = await c.get("/api/emails", params={"package_id": ids["package"]})
        assert log.status_code == 200 and len(log.json()) == 1


async def test_edit_draft(emails_client):
    client, ids = emails_client
    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        patched = await c.patch(f"/api/emails/{email_id}", json={"subject": "Custom RFQ"})
        assert patched.status_code == 200
        assert patched.json()["subject"] == "Custom RFQ"


async def test_edit_draft_cc_bcc_roundtrip(emails_client):
    client, ids = emails_client
    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        patched = await c.patch(
            f"/api/emails/{email_id}",
            json={"cc": ["c@x.test"], "bcc": ["b@x.test"]})
        assert patched.status_code == 200, patched.text
        got = await c.get(f"/api/emails/{email_id}")
        assert got.status_code == 200
        assert got.json()["cc"] == ["c@x.test"]
        assert got.json()["bcc"] == ["b@x.test"]


async def test_send_returns_503_when_smtp_not_configured(emails_client):
    client, ids = emails_client
    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        # Test settings have no SMTP host/user => SMTPSender.is_configured() False
        send = await c.post(f"/api/emails/{email_id}/send")
        assert send.status_code == 503, send.text


async def test_send_succeeds_with_injected_sender(emails_client, monkeypatch):
    import app.api.emails as emails_api

    client, ids = emails_client

    class _FakeSender:
        def is_configured(self):
            return True

        def send(self, **kwargs):
            return "<msgid@test>"

    monkeypatch.setattr(emails_api, "SMTPSender", lambda: _FakeSender())

    async with client as c:
        rfq = await c.post(
            f"/api/projects/{ids['project']}/packages/{ids['package']}/rfq",
            json={"supplier_ids": [ids["supplier"]]})
        email_id = rfq.json()["email_ids"][0]
        send = await c.post(f"/api/emails/{email_id}/send")
        assert send.status_code == 200, send.text
        assert send.json()["status"] == "sent"
        assert send.json()["message_id"] == "<msgid@test>"


async def test_rfq_404_missing_package(emails_client):
    client, ids = emails_client
    async with client as c:
        r = await c.post(
            f"/api/projects/{ids['project']}/packages/999999/rfq",
            json={"supplier_ids": [ids["supplier"]]})
    assert r.status_code == 404
