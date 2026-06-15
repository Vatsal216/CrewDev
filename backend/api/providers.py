from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import get_db
from core.llm import provider_store

router = APIRouter()


class CreateProviderReq(BaseModel):
    provider: str
    label: str
    config: dict
    enabled: bool = True
    is_default: bool = False


class UpdateProviderReq(BaseModel):
    label: Optional[str] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    config: Optional[dict] = None


class DefaultModelReq(BaseModel):
    value: str


@router.get("/api/providers")
async def list_providers(db: AsyncSession = Depends(get_db)):
    rows = await provider_store.list_providers(db)
    return [provider_store.public_view(r) for r in rows]


@router.post("/api/providers")
async def create_provider(req: CreateProviderReq, db: AsyncSession = Depends(get_db)):
    if req.provider not in provider_store.REQUIRED_FIELDS:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    row = await provider_store.create_provider(
        db, provider=req.provider, label=req.label, config=req.config,
        enabled=req.enabled, is_default=req.is_default,
    )
    return provider_store.public_view(row)


@router.patch("/api/providers/{provider_id}")
async def update_provider(provider_id: str, req: UpdateProviderReq, db: AsyncSession = Depends(get_db)):
    row = await provider_store.update_provider(
        db, provider_id, label=req.label, enabled=req.enabled,
        is_default=req.is_default, config_updates=req.config,
    )
    if not row:
        raise HTTPException(404, "Provider not found")
    return provider_store.public_view(row)


@router.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    if not await provider_store.delete_provider(db, provider_id):
        raise HTTPException(404, "Provider not found")
    return {"ok": True}


@router.post("/api/providers/{provider_id}/test")
async def test_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    row = await provider_store.get_provider(db, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    return await provider_store.test_connection(row)


@router.get("/api/providers/{provider_id}/models")
async def provider_models(provider_id: str, db: AsyncSession = Depends(get_db)):
    row = await provider_store.get_provider(db, provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    return {"models": await provider_store.available_models(row)}


@router.get("/api/settings/default-model")
async def get_default_model(db: AsyncSession = Depends(get_db)):
    return {"value": await provider_store.get_default_model(db)}


@router.put("/api/settings/default-model")
async def put_default_model(req: DefaultModelReq, db: AsyncSession = Depends(get_db)):
    # Expected format: "{provider_config_id}::{model_name}" (both parts non-empty).
    left, sep, right = req.value.partition("::")
    if not (sep and left and right):
        raise HTTPException(400, "default-model must be '<provider_config_id>::<model_name>'")
    await provider_store.set_default_model(db, req.value)
    return {"value": req.value}
