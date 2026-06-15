import httpx
from httpx import ASGITransport
from fastapi import FastAPI
from api.skills import router
from db.models import get_db


def _client(db_session):
    app = FastAPI(); app.include_router(router)
    async def _o(): yield db_session
    app.dependency_overrides[get_db] = _o
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_skills_crud(db_session):
    async with _client(db_session) as client:
        s = (await client.post("/api/skills", json={"name": "Reviewer", "description": "d", "instructions": "i"})).json()
        assert s["name"] == "Reviewer" and s["enabled"] is True
        assert len((await client.get("/api/skills")).json()) == 1
        patched = (await client.patch(f"/api/skills/{s['id']}", json={"enabled": False})).json()
        assert patched["enabled"] is False
        assert (await client.delete(f"/api/skills/{s['id']}")).json()["ok"] is True


async def test_skill_requires_name(db_session):
    async with _client(db_session) as client:
        assert (await client.post("/api/skills", json={"name": "  "})).status_code == 400
        assert (await client.patch("/api/skills/nope", json={"name": "x"})).status_code == 404
