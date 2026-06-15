import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import get_db, Skill

router = APIRouter()


def _json(s: Skill) -> dict:
    return {"id": s.id, "name": s.name, "description": s.description,
            "instructions": s.instructions, "enabled": s.enabled,
            "created_at": s.created_at.isoformat(), "updated_at": s.updated_at.isoformat()}


class CreateSkillReq(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    enabled: bool = True


class UpdateSkillReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/api/skills")
async def list_skills(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Skill).order_by(Skill.created_at))
    return [_json(s) for s in res.scalars().all()]


@router.post("/api/skills")
async def create_skill(req: CreateSkillReq, db: AsyncSession = Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(400, "Skill name is required")
    s = Skill(id=str(uuid.uuid4()), name=req.name.strip(), description=req.description,
              instructions=req.instructions, enabled=req.enabled)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _json(s)


@router.patch("/api/skills/{sid}")
async def update_skill(sid: str, req: UpdateSkillReq, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Skill).where(Skill.id == sid))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Skill not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return _json(s)


@router.delete("/api/skills/{sid}")
async def delete_skill(sid: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Skill).where(Skill.id == sid))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Skill not found")
    await db.delete(s)
    await db.commit()
    return {"ok": True}
