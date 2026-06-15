import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ProviderConfig, AppSetting
from core.llm import crypto

REQUIRED_FIELDS = {
    "anthropic": ["api_key"],
    "openai": ["api_key"],
    "azure": ["api_key", "api_base", "api_version"],
    "ollama": ["api_base"],
}
SECRET_FIELDS = {"api_key"}
DEFAULT_MODEL_KEY = "default_model"
CURATED_MODELS = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
    "azure": [],   # deployment names are user-defined
    "ollama": [],  # fetched live
}


def normalize_ollama_base(api_base: str) -> str:
    """Return the Ollama server root, not the /api endpoint.

    Accepted user inputs:
    - http://localhost:11434
    - http://localhost:11434/api
    - https://ollama.com
    - https://ollama.com/api
    """
    base = (api_base or "").strip().rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return base


def is_ollama_cloud(api_base: str) -> bool:
    """Detect the hosted Ollama API endpoint so we can require auth there only."""
    return "ollama.com" in normalize_ollama_base(api_base).lower()


async def _clear_other_defaults(db: AsyncSession, keep_id: str):
    res = await db.execute(select(ProviderConfig).where(ProviderConfig.is_default == True))  # noqa: E712
    for r in res.scalars().all():
        if r.id != keep_id:
            r.is_default = False


async def create_provider(db, *, provider, label, config, enabled=True, is_default=False):
    row = ProviderConfig(
        id=str(uuid.uuid4()),
        provider=provider,
        label=label,
        enabled=enabled,
        is_default=is_default,
        config_encrypted=crypto.encrypt(config),
    )
    db.add(row)
    if is_default:
        await _clear_other_defaults(db, row.id)
    await db.commit()
    await db.refresh(row)
    return row


async def list_providers(db):
    res = await db.execute(select(ProviderConfig).order_by(ProviderConfig.created_at))
    return list(res.scalars().all())


async def get_provider(db, provider_id):
    res = await db.execute(select(ProviderConfig).where(ProviderConfig.id == provider_id))
    return res.scalar_one_or_none()


async def update_provider(db, provider_id, *, label=None, enabled=None, is_default=None, config_updates=None):
    row = await get_provider(db, provider_id)
    if not row:
        return None
    if label is not None:
        row.label = label
    if enabled is not None:
        row.enabled = enabled
    if config_updates:
        cfg = crypto.decrypt(row.config_encrypted)
        cfg.update({k: v for k, v in config_updates.items() if v is not None})
        row.config_encrypted = crypto.encrypt(cfg)
    if is_default is True:
        row.is_default = True
        await _clear_other_defaults(db, row.id)
    elif is_default is False:
        row.is_default = False
    await db.commit()
    await db.refresh(row)
    return row


async def delete_provider(db, provider_id) -> bool:
    row = await get_provider(db, provider_id)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True


def decrypt_config(row) -> dict:
    return crypto.decrypt(row.config_encrypted)


def public_view(row) -> dict:
    cfg = crypto.decrypt(row.config_encrypted)
    return {
        "id": row.id,
        "provider": row.provider,
        "label": row.label,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "has_key": bool(cfg.get("api_key")),
        "key_masked": crypto.mask(cfg.get("api_key", "")),
        "config": {k: v for k, v in cfg.items() if k not in SECRET_FIELDS},
    }


async def get_default_model(db):
    res = await db.execute(select(AppSetting).where(AppSetting.key == DEFAULT_MODEL_KEY))
    row = res.scalar_one_or_none()
    return row.value if row else None


async def set_default_model(db, value: str):
    res = await db.execute(select(AppSetting).where(AppSetting.key == DEFAULT_MODEL_KEY))
    row = res.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=DEFAULT_MODEL_KEY, value=value))
    await db.commit()


async def available_models(row) -> list:
    if row.provider == "ollama":
        cfg = crypto.decrypt(row.config_encrypted)
        base = normalize_ollama_base(cfg.get("api_base") or "")
        api_key = (cfg.get("api_key") or "").strip()
        if not base:
            return []
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{base}/api/tags", headers=headers)
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []
    return list(CURATED_MODELS.get(row.provider, []))


async def test_connection(row) -> dict:
    """Lightweight check: required fields present, and (Ollama) reachable.
    Does not spend tokens — a full generation ping is intentionally avoided."""
    cfg = crypto.decrypt(row.config_encrypted)
    missing = [f for f in REQUIRED_FIELDS.get(row.provider, []) if not cfg.get(f)]
    if row.provider == "ollama" and is_ollama_cloud(cfg.get("api_base") or "") and not cfg.get("api_key"):
        missing.append("api_key")
    if missing:
        return {"ok": False, "code": "not_configured", "message": f"Missing: {', '.join(missing)}"}
    if row.provider == "ollama" and not await available_models(row):
        return {"ok": False, "code": "connection", "message": "Ollama not reachable, authentication failed, or no models are available."}
    return {"ok": True, "code": "ok", "message": "Configured."}


async def seed_default_from_env(db, settings) -> bool:
    """Seed one default provider from env if none exist (backward compat). Idempotent."""
    if await list_providers(db):
        return False
    if settings.anthropic_api_key:
        row = await create_provider(db, provider="anthropic", label="Anthropic (env)",
                                    config={"api_key": settings.anthropic_api_key}, is_default=True)
        await set_default_model(db, f"{row.id}::{settings.llm_model}")
        return True
    if getattr(settings, "openai_api_key", ""):
        row = await create_provider(db, provider="openai", label="OpenAI (env)",
                                    config={"api_key": settings.openai_api_key}, is_default=True)
        await set_default_model(db, f"{row.id}::gpt-4o")
        return True
    ollama_base = getattr(settings, "ollama_base_url", "")
    ollama_key = getattr(settings, "ollama_api_key", "")
    if ollama_base or ollama_key:
        await create_provider(
            db,
            provider="ollama",
            label="Ollama (env)",
            config={"api_base": ollama_base or "https://ollama.com", "api_key": ollama_key},
            is_default=True,
        )
        return True
    return False
