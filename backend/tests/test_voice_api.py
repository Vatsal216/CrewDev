import httpx
from httpx import ASGITransport
from fastapi import FastAPI
import litellm

from api.voice import router
from db.models import get_db
from core.llm import provider_store


def _client(db_session):
    app = FastAPI()
    app.include_router(router)

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


class _Result:
    text = "hello from whisper"


async def test_transcribe_with_openai_provider(monkeypatch, db_session):
    await provider_store.create_provider(db_session, provider="openai", label="O", config={"api_key": "sk-k"})

    async def fake_atranscription(**kwargs):
        return _Result()

    monkeypatch.setattr(litellm, "atranscription", fake_atranscription)

    async with _client(db_session) as client:
        r = await client.post("/api/voice/transcribe", files={"audio": ("a.webm", b"xxxx", "audio/webm")})
        assert r.status_code == 200
        assert r.json()["text"] == "hello from whisper"


async def test_transcribe_without_openai_provider_returns_400(db_session):
    async with _client(db_session) as client:
        r = await client.post("/api/voice/transcribe", files={"audio": ("a.webm", b"xxxx", "audio/webm")})
        assert r.status_code == 400
        assert "not_configured" in r.text
