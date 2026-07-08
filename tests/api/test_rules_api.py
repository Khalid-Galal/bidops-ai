import httpx
import pytest


@pytest.fixture
def rules_client(tmp_path, monkeypatch):
    """ASGI client with the rules service pointed at a temp user-override file."""
    import app.api.rules as rules_api
    from app.services.rules.rules_service import RulesService

    svc = RulesService(user_path=tmp_path / "rules.json")
    monkeypatch.setattr(rules_api, "get_rules_service", lambda: svc)

    from app.main import app
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_get_rules_returns_defaults(rules_client):
    async with rules_client as client:
        r = await client.get("/api/rules")
    assert r.status_code == 200
    body = r.json()
    assert body["commercial"]["currency"] == "USD"
    assert body["email"]["default_language"] == "en"


async def test_put_rules_persists_and_get_reflects(rules_client):
    async with rules_client as client:
        current = (await client.get("/api/rules")).json()
        current["commercial"]["currency"] = "EGP"
        current["commercial"]["vat_rate"] = 0.14
        put = await client.put("/api/rules", json=current)
        assert put.status_code == 200
        after = (await client.get("/api/rules")).json()
    assert after["commercial"]["currency"] == "EGP"
    assert after["commercial"]["vat_rate"] == 0.14
    assert after["measurement"]["unit_mappings"]["sqm"] == "m2"


async def test_put_rules_rejects_typo_key(rules_client):
    async with rules_client as client:
        current = (await client.get("/api/rules")).json()
        current["commercial"]["vat_rat"] = 0.14  # typo of vat_rate
        put = await client.put("/api/rules", json=current)
    assert put.status_code == 422
