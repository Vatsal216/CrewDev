import httpx
from httpx import ASGITransport
from fastapi import FastAPI

from api.exec import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_exec_runs_python():
    async with _client() as client:
        r = await client.post("/api/exec", json={"code": "print(2 + 2)"})
        assert r.status_code == 200
        body = r.json()
        assert "4" in body["stdout"]
        assert body["exit_code"] == 0


async def test_exec_empty_code_400():
    async with _client() as client:
        r = await client.post("/api/exec", json={"code": "   "})
        assert r.status_code == 400


async def test_exec_collects_image_artifact():
    async with _client() as client:
        code = "open('plot.png','wb').write(b'\\x89PNG\\r\\n')"
        r = await client.post("/api/exec", json={"code": code})
        arts = r.json()["artifacts"]
        assert any(a["name"] == "plot.png" and a["is_image"] for a in arts)
