import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import get_db, Project, ChatSession, CodeSession, CodeMessage
from projects.manager import ProjectManager

router = APIRouter()


def _code_json(s: CodeSession) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "project_id": s.project_id,
        "chat_session_id": s.chat_session_id,
        "model": s.model,
        "model_provider_id": s.model_provider_id,
        "engine": s.engine,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


class CreateCodeReq(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class UpdateCodeReq(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    model_provider_id: Optional[str] = None
    engine: Optional[str] = None


async def _get_code_session(db: AsyncSession, sid: str) -> CodeSession:
    res = await db.execute(select(CodeSession).where(CodeSession.id == sid))
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(404, "Code workspace not found")
    return sess


async def _seed_code_workspace(project: Project, title: str, description: str = "") -> None:
    workspace = Path(project.workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)
    readme = workspace / "README.md"
    agents = workspace / "AGENTS.md"
    if not readme.exists():
        readme.write_text(
            f"# {title}\n\n"
            f"{description or 'Code workspace created from the Code tab.'}\n\n"
            "Use the Code agent chat to create, edit, inspect, and validate files in this workspace.\n",
            encoding="utf-8",
        )
    if not agents.exists():
        agents.write_text(
            "# Code Agent Instructions\n\n"
            "You are working inside a dedicated Code workspace.\n"
            "- Inspect the existing files before changing them.\n"
            "- Keep changes scoped to this workspace.\n"
            "- Prefer small, verifiable edits.\n"
            "- Run safe validation commands when useful.\n"
            "- Summarize changed files and validation results at the end.\n",
            encoding="utf-8",
        )


@router.post("/api/code")
async def create_code_workspace(req: CreateCodeReq, db: AsyncSession = Depends(get_db)):
    title = req.title or "New code workspace"
    pm = ProjectManager(db)
    project = await pm.create_project(title, req.description or "Dedicated Code workspace")
    project.meta = {"source": "code"}

    chat_session = ChatSession(
        id=str(uuid.uuid4()),
        project_id=project.id,
        title="Code agent",
        engine="crewai",
    )
    code_session = CodeSession(
        id=str(uuid.uuid4()),
        title=title,
        project_id=project.id,
        chat_session_id=chat_session.id,
        engine="crewai",
    )
    db.add(chat_session)
    db.add(code_session)
    await db.commit()
    await db.refresh(project)
    await db.refresh(code_session)
    await _seed_code_workspace(project, title, req.description or "")
    return _code_json(code_session)


@router.get("/api/code")
async def list_code_workspaces(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CodeSession).order_by(CodeSession.updated_at.desc()))
    return [_code_json(s) for s in res.scalars().all()]


@router.get("/api/code/{sid}")
async def get_code_workspace(sid: str, db: AsyncSession = Depends(get_db)):
    return _code_json(await _get_code_session(db, sid))


@router.patch("/api/code/{sid}")
async def update_code_workspace(sid: str, req: UpdateCodeReq, db: AsyncSession = Depends(get_db)):
    sess = await _get_code_session(db, sid)
    data = req.model_dump(exclude_unset=True)
    if "engine" in data and data["engine"] not in {"crewai", "deepagents"}:
        raise HTTPException(400, "engine must be 'crewai' or 'deepagents'")

    for key, value in data.items():
        setattr(sess, key, value)

    # Keep the underlying project chat session in sync. The Code pipeline is
    # separate in the UI/API, but it delegates execution to the existing project
    # agent engine for file tools and validation.
    res = await db.execute(select(ChatSession).where(ChatSession.id == sess.chat_session_id))
    chat = res.scalar_one_or_none()
    if chat:
        if "title" in data:
            chat.title = data["title"] or chat.title
        if "model" in data:
            chat.model = data["model"]
        if "model_provider_id" in data:
            chat.model_provider_id = data["model_provider_id"]
        if "engine" in data:
            chat.engine = data["engine"]

    await db.commit()
    await db.refresh(sess)
    return _code_json(sess)


@router.delete("/api/code/{sid}")
async def delete_code_workspace(sid: str, db: AsyncSession = Depends(get_db)):
    sess = await _get_code_session(db, sid)
    project_id = sess.project_id
    await db.delete(sess)
    await db.commit()

    # Remove the hidden project/workspace created for this Code session.
    pm = ProjectManager(db)
    await pm.delete_project(project_id)
    return {"ok": True}


@router.get("/api/code/{sid}/messages")
async def code_messages(sid: str, db: AsyncSession = Depends(get_db)):
    await _get_code_session(db, sid)
    res = await db.execute(
        select(CodeMessage).where(CodeMessage.session_id == sid).order_by(CodeMessage.created_at)
    )
    return [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat(),
    } for m in res.scalars().all()]
