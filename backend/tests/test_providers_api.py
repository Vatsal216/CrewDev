import httpx
from httpx import ASGITransport
from fastapi import FastAPI

from api.providers import router
from db.models import get_db


def _client(db_session):
    app = FastAPI()
    app.include_router(router)

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_create_list_mask(db_session):
    async with _client(db_session) as client:
        r = await client.post("/api/providers", json={
            "provider": "openai", "label": "OAI", "config": {"api_key": "sk-abcdefgh"},
        })
        assert r.status_code == 200
        body = r.json()
        assert body["has_key"] is True
        assert body["key_masked"] == "sk-…efgh"
        assert "sk-abcdefgh" not in r.text

        lst = (await client.get("/api/providers")).json()
        assert len(lst) == 1


async def test_unknown_provider_rejected(db_session):
    async with _client(db_session) as client:
        r = await client.post("/api/providers", json={"provider": "cohere", "label": "C", "config": {}})
        assert r.status_code == 400


async def test_default_model_endpoints(db_session):
    async with _client(db_session) as client:
        assert (await client.get("/api/settings/default-model")).json()["value"] is None
        await client.put("/api/settings/default-model", json={"value": "pid::gpt-4o"})
        assert (await client.get("/api/settings/default-model")).json()["value"] == "pid::gpt-4o"


async def test_test_endpoint(db_session):
    async with _client(db_session) as client:
        created = (await client.post("/api/providers", json={
            "provider": "openai", "label": "OAI", "config": {"api_key": "sk-x"},
        })).json()
        res = (await client.post(f"/api/providers/{created['id']}/test")).json()
        assert res["ok"] is True


async def test_patch_updates_and_reencrypts(db_session):
    async with _client(db_session) as client:
        created = (await client.post("/api/providers", json={
            "provider": "openai", "label": "OAI", "config": {"api_key": "sk-old"},
        })).json()
        patched = (await client.patch(f"/api/providers/{created['id']}", json={
            "label": "OAI-2", "config": {"api_key": "sk-new12345"},
        })).json()
        assert patched["label"] == "OAI-2"
        assert patched["key_masked"] == "sk-…2345"
        assert "sk-new12345" not in (await client.get("/api/providers")).text


async def test_patch_and_delete_404(db_session):
    async with _client(db_session) as client:
        assert (await client.patch("/api/providers/nope", json={"label": "x"})).status_code == 404
        assert (await client.delete("/api/providers/nope")).status_code == 404


async def test_malformed_default_model_rejected(db_session):
    async with _client(db_session) as client:
        assert (await client.put("/api/settings/default-model", json={"value": "gpt-4o"})).status_code == 400
        assert (await client.put("/api/settings/default-model", json={"value": "::gpt-4o"})).status_code == 400
