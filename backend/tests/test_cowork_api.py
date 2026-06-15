import httpx
from httpx import ASGITransport
from fastapi import FastAPI

from api.cowork import router
from db.models import get_db


def _client(db_session):
    app = FastAPI()
    app.include_router(router)

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_cowork_crud_and_doc(db_session):
    async with _client(db_session) as client:
        s = (await client.post("/api/cowork", json={"title": "WS"})).json()
        assert s["title"] == "WS" and s["doc_content"] == ""
        assert len((await client.get("/api/cowork")).json()) == 1

        await client.put(f"/api/cowork/{s['id']}/doc", json={"content": "# Doc"})
        assert (await client.get(f"/api/cowork/{s['id']}")).json()["doc_content"] == "# Doc"

        patched = (await client.patch(f"/api/cowork/{s['id']}", json={"model": "gpt-4o", "model_provider_id": "p1"})).json()
        assert patched["model"] == "gpt-4o"

        assert (await client.get(f"/api/cowork/{s['id']}/messages")).json() == []
        assert (await client.delete(f"/api/cowork/{s['id']}")).json()["ok"] is True


async def test_cowork_404(db_session):
    async with _client(db_session) as client:
        assert (await client.get("/api/cowork/nope")).status_code == 404
        assert (await client.put("/api/cowork/nope/doc", json={"content": "x"})).status_code == 404
