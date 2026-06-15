import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import get_db, CoworkSession, CoworkMessage

router = APIRouter()


def _session_json(s: CoworkSession) -> dict:
    return {
        "id": s.id, "title": s.title, "doc_content": s.doc_content,
        "model": s.model, "model_provider_id": s.model_provider_id,
        "created_at": s.created_at.isoformat(), "updated_at": s.updated_at.isoformat(),
    }


class CreateCoworkReq(BaseModel):
    title: Optional[str] = None


class UpdateCoworkReq(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    model_provider_id: Optional[str] = None


class DocReq(BaseModel):
    content: str


async def _get(db, sid) -> CoworkSession:
    res = await db.execute(select(CoworkSession).where(CoworkSession.id == sid))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Cowork session not found")
    return s


@router.post("/api/cowork")
async def create_cowork(req: CreateCoworkReq, db: AsyncSession = Depends(get_db)):
    s = CoworkSession(id=str(uuid.uuid4()), title=req.title or "New workspace", doc_content="")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _session_json(s)


@router.get("/api/cowork")
async def list_cowork(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CoworkSession).order_by(CoworkSession.updated_at.desc()))
    return [_session_json(s) for s in res.scalars().all()]


@router.get("/api/cowork/{sid}")
async def get_cowork(sid: str, db: AsyncSession = Depends(get_db)):
    return _session_json(await _get(db, sid))


@router.patch("/api/cowork/{sid}")
async def update_cowork(sid: str, req: UpdateCoworkReq, db: AsyncSession = Depends(get_db)):
    s = await _get(db, sid)
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return _session_json(s)


@router.delete("/api/cowork/{sid}")
async def delete_cowork(sid: str, db: AsyncSession = Depends(get_db)):
    s = await _get(db, sid)
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.get("/api/cowork/{sid}/messages")
async def cowork_messages(sid: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(CoworkMessage).where(CoworkMessage.session_id == sid).order_by(CoworkMessage.created_at)
    )
    return [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in res.scalars().all()]


@router.put("/api/cowork/{sid}/doc")
async def save_doc(sid: str, req: DocReq, db: AsyncSession = Depends(get_db)):
    s = await _get(db, sid)
    s.doc_content = req.content
    await db.commit()
    return {"ok": True}
