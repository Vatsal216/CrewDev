import httpx
from httpx import ASGITransport
from fastapi import FastAPI
from api.attachments import router


def _client():
    app = FastAPI(); app.include_router(router)
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_upload_text_and_image():
    async with _client() as client:
        r = await client.post("/api/attachments", files=[
            ("files", ("a.md", b"# Title", "text/markdown")),
            ("files", ("p.png", b"\x89PNG\r\n", "image/png")),
        ])
        assert r.status_code == 200
        out = r.json()
        kinds = {a["name"]: a["kind"] for a in out}
        assert kinds["a.md"] == "text" and kinds["p.png"] == "image"
