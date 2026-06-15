import litellm
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import get_db
from core.llm import provider_store

router = APIRouter()


async def _openai_key(db) -> str | None:
    for p in await provider_store.list_providers(db):
        if p.provider == "openai" and p.enabled:
            cfg = provider_store.decrypt_config(p)
            if cfg.get("api_key"):
                return cfg["api_key"]
    return None


@router.post("/api/voice/transcribe")
async def transcribe(audio: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    key = await _openai_key(db)
    if not key:
        raise HTTPException(400, "not_configured: add an OpenAI provider in Settings to use server transcription.")
    data = await audio.read()
    try:
        result = await litellm.atranscription(
            model="whisper-1",
            file=(audio.filename or "audio.webm", data),
            api_key=key,
        )
    except Exception as e:
        raise HTTPException(502, f"Transcription failed: {str(e)[:200]}")
    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text", "")
    return {"text": text or ""}
