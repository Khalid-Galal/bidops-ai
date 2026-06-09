import httpx
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def offers_client(tmp_path, monkeypatch):
    # Save uploaded offer files under tmp, not the repo's data/ dir.
    monkeypatch.chdir(tmp_path)
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
        package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP", trade_category="mep")
        seed.add(package)
        seed.add(Supplier(name="CoolAir", emails=["s@coolair.test"], trade_categories=["mep"]))
        await seed.commit()
        sup = (await seed.execute(select(Supplier))).scalars().first()
        ids = {"project": project.id, "package": package.id, "supplier": sup.id}

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, ids
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_ingest_list_patch_detail(offers_client):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    async with client as c:
        up = await c.post(
            base,
            data={"supplier_id": str(ids["supplier"])},
            files={"files": ("offer.txt", b"price 100000 usd", "text/plain")},
        )
        assert up.status_code == 201, up.text
        offer_id = up.json()["id"]
        assert up.json()["status"] == "received"

        lst = await c.get(base)
        assert lst.status_code == 200 and len(lst.json()) == 1

        patched = await c.patch(f"/api/offers/{offer_id}",
                                json={"total_price": 100000, "currency": "USD", "delivery_weeks": 6})
        assert patched.status_code == 200
        assert patched.json()["total_price"] == 100000

        detail = await c.get(f"/api/offers/{offer_id}")
        assert detail.status_code == 200
        assert detail.json()["supplier_name"] == "CoolAir"
        assert (await c.get("/api/offers/999999")).status_code == 404


async def test_score_compare_and_xlsx(offers_client):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    async with client as c:
        # two offers via ingest + manual price
        for price, weeks in ((100000, 4), (150000, 8)):
            up = await c.post(base, data={"supplier_id": str(ids["supplier"])},
                              files={"files": ("o.txt", b"x", "text/plain")})
            oid = up.json()["id"]
            await c.patch(f"/api/offers/{oid}", json={"total_price": price, "delivery_weeks": weeks})

        score = await c.post(f"{base}/score")
        assert score.status_code == 200, score.text
        assert score.json()["offers_scored"] == 2
        assert score.json()["ranking"][0]["rank"] == 1

        cmp = await c.get(f"{base}/comparison")
        assert cmp.status_code == 200
        assert cmp.json()["total_offers"] == 2
        assert cmp.json()["price_min"] == 100000

        xlsx = await c.get(f"{base}/comparison.xlsx")
        assert xlsx.status_code == 200
        assert xlsx.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert len(xlsx.content) > 0


async def test_select_and_clarification(offers_client):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    async with client as c:
        up = await c.post(base, data={"supplier_id": str(ids["supplier"])},
                          files={"files": ("o.txt", b"x", "text/plain")})
        oid = up.json()["id"]
        sel = await c.post(f"/api/offers/{oid}/select", json={"notes": "winner"})
        assert sel.status_code == 200 and sel.json()["status"] == "selected"

        clar = await c.post(f"/api/offers/{oid}/clarification",
                            json={"items": ["Confirm delivery"]})
        assert clar.status_code == 201, clar.text
        assert clar.json()["email_type"] == "clarification"
        assert clar.json()["status"] == "draft"
        assert "Confirm delivery" in clar.json()["body_html"]


async def test_extract_returns_503_without_llm(offers_client, monkeypatch):
    client, ids = offers_client
    base = f"/api/projects/{ids['project']}/packages/{ids['package']}/offers"
    import app.api.offers as offers_api
    from app.services.offer.offer_extractor import LLMUnavailable

    class _NoLLM:
        async def extract_offer(self, db, offer_id):
            raise LLMUnavailable("no key")

    # monkeypatch auto-restores the real class after the test (no leakage).
    monkeypatch.setattr(offers_api, "OfferExtractor", lambda: _NoLLM())
    async with client as c:
        up = await c.post(base, data={"supplier_id": str(ids["supplier"])},
                          files={"files": ("o.txt", b"x", "text/plain")})
        oid = up.json()["id"]
        r = await c.post(f"/api/offers/{oid}/extract")
        assert r.status_code == 503


async def test_score_404_missing_package(offers_client):
    client, ids = offers_client
    async with client as c:
        r = await c.post(f"/api/projects/{ids['project']}/packages/999999/offers/score")
    assert r.status_code == 404
