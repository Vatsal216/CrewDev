import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    init_db,
    get_db,
    AsyncSessionLocal,
    ChatMessage,
    ChatSession,
    Project,
    GeneralChatSession,
    GeneralChatMessage,
    ChatMemory,
    CoworkSession,
    CoworkMessage,
    CodeSession,
    CodeMessage,
)
from core.general_chat_orchestrator import GeneralChatOrchestrator, auto_title, memory_candidate
from core.general_agent_orchestrator import GeneralAgentOrchestrator
from core.cowork_orchestrator import CoworkOrchestrator
from core.skills import select_skills, build_skills_block
from config import settings
from core.llm import selection as selection_mod, provider_store
from core.llm.types import LLMError


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        await provider_store.seed_default_from_env(db, settings)
    yield


app = FastAPI(title="CrewDev Platform", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.providers import router as providers_router
app.include_router(providers_router)

from api.voice import router as voice_router
app.include_router(voice_router)

from api.cowork import router as cowork_router
app.include_router(cowork_router)

from api.code import router as code_router
app.include_router(code_router)

from api.exec import router as exec_router
app.include_router(exec_router)

from api.skills import router as skills_router
app.include_router(skills_router)

from api.attachments import router as attachments_router
app.include_router(attachments_router)


# ─── Helpers ───────────────────────────────────────────────────

def project_to_json(p: Project):
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "indexed": p.indexed,
        "index_status": p.index_status,
        "created_at": p.created_at.isoformat(),
    }


def chat_to_json(c: GeneralChatSession):
    return {
        "id": c.id,
        "title": c.title,
        "pinned": c.pinned,
        "archived": c.archived,
        "memory_enabled": c.memory_enabled,
        "web_enabled": c.web_enabled,
        "agent_enabled": c.agent_enabled,
        "mode": c.mode,
        "model": c.model,
        "model_provider_id": c.model_provider_id,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def chat_message_to_json(m: GeneralChatMessage):
    return {
        "id": m.id,
        "chat_id": m.chat_id,
        "role": m.role,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat(),
    }


def memory_to_json(m: ChatMemory):
    return {
        "id": m.id,
        "memory_type": m.memory_type,
        "content": m.content,
        "source_chat_id": m.source_chat_id,
        "source_message_id": m.source_message_id,
        "confidence": m.confidence,
        "enabled": m.enabled,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }


# ─── Project endpoints ─────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


@app.post("/api/projects")
async def create_project(req: CreateProjectRequest, db: AsyncSession = Depends(get_db)):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    project = await pm.create_project(req.name, req.description)
    return project_to_json(project)


@app.get("/api/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    projects = await pm.list_projects()
    visible = [p for p in projects if not ((p.meta or {}).get("source") == "code")]
    return [project_to_json(p) for p in visible]


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    p = await pm.get_project(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "indexed": p.indexed,
        "index_status": p.index_status,
        "workspace_path": p.workspace_path,
        "created_at": p.created_at.isoformat(),
    }


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    await pm.delete_project(project_id)
    return {"ok": True}


@app.get("/api/projects/{project_id}/files")
async def get_file_tree(project_id: str, db: AsyncSession = Depends(get_db)):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    tree = await pm.get_file_tree(project_id)
    return {"tree": tree}


@app.post("/api/projects/{project_id}/upload")
async def upload_files(
    project_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    project = await pm.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    saved = []
    for f in files:
        content = await f.read()
        rel_path = await pm.save_uploaded_file(project_id, f.filename, content)
        saved.append(rel_path)

    return {"saved": saved, "count": len(saved)}


@app.post("/api/projects/{project_id}/index")
async def index_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    from projects.manager import ProjectManager, ProjectIndexer
    pm = ProjectManager(db)
    project = await pm.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    project.index_status = "indexing"
    await db.commit()

    workspace_path = project.workspace_path

    async def _do_index():
        indexer = ProjectIndexer(project_id)
        try:
            count = await indexer.index(workspace_path)
            async with AsyncSessionLocal() as s:
                res = await s.execute(select(Project).where(Project.id == project_id))
                p = res.scalar_one_or_none()
                if p:
                    p.indexed = True
                    p.index_status = "done"
                    p.meta = {"indexed_chunks": count}
                    await s.commit()
        except Exception as e:
            async with AsyncSessionLocal() as s:
                res = await s.execute(select(Project).where(Project.id == project_id))
                p = res.scalar_one_or_none()
                if p:
                    p.index_status = f"error: {str(e)[:100]}"
                    await s.commit()

    background_tasks.add_task(_do_index)
    return {"status": "indexing_started"}


# ─── Project session endpoints ─────────────────────────────────

@app.post("/api/projects/{project_id}/sessions")
async def create_session(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    session = ChatSession(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title="New chat",
    )
    db.add(session)
    await db.commit()
    return {"id": session.id, "project_id": project_id, "title": session.title}


@app.get("/api/projects/{project_id}/sessions")
async def list_sessions(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.project_id == project_id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    model_provider_id: Optional[str] = None
    engine: Optional[str] = None


@app.patch("/api/projects/{project_id}/sessions/{session_id}")
async def update_project_session(project_id: str, session_id: str,
                                 req: UpdateSessionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.project_id == project_id,
        )
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(404, "Session not found")
    data = req.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(sess, key, value)
    await db.commit()
    await db.refresh(sess)
    return {
        "id": sess.id,
        "project_id": sess.project_id,
        "title": sess.title,
        "model": sess.model,
        "model_provider_id": sess.model_provider_id,
        "engine": sess.engine,
    }


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    msgs = result.scalars().all()
    return [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat(),
    } for m in msgs]


# ─── General chat endpoints ────────────────────────────────────

class CreateChatRequest(BaseModel):
    title: Optional[str] = None
    memory_enabled: bool = True
    web_enabled: bool = False
    agent_enabled: bool = False
    mode: str = "direct"


class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    memory_enabled: Optional[bool] = None
    web_enabled: Optional[bool] = None
    agent_enabled: Optional[bool] = None
    mode: Optional[str] = None
    model: Optional[str] = None
    model_provider_id: Optional[str] = None


@app.post("/api/chats")
async def create_general_chat(req: CreateChatRequest, db: AsyncSession = Depends(get_db)):
    chat = GeneralChatSession(
        id=str(uuid.uuid4()),
        title=req.title or "New chat",
        memory_enabled=req.memory_enabled,
        web_enabled=req.web_enabled,
        agent_enabled=req.agent_enabled,
        mode="agent" if req.agent_enabled else "direct",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat_to_json(chat)


@app.get("/api/chats")
async def list_general_chats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GeneralChatSession)
        .where(GeneralChatSession.archived == False)  # noqa: E712
        .order_by(GeneralChatSession.pinned.desc(), GeneralChatSession.updated_at.desc())
    )
    chats = result.scalars().all()
    return [chat_to_json(c) for c in chats]


@app.get("/api/chats/{chat_id}")
async def get_general_chat(chat_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GeneralChatSession).where(GeneralChatSession.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat_to_json(chat)


@app.patch("/api/chats/{chat_id}")
async def update_general_chat(chat_id: str, req: UpdateChatRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GeneralChatSession).where(GeneralChatSession.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Chat not found")

    data = req.model_dump(exclude_unset=True)
    if "agent_enabled" in data and "mode" not in data:
        data["mode"] = "agent" if data["agent_enabled"] else "direct"
    if "mode" in data:
        data["mode"] = "agent" if data["mode"] == "agent" else "direct"
        data["agent_enabled"] = data["mode"] == "agent"
    for key, value in data.items():
        setattr(chat, key, value)
    await db.commit()
    await db.refresh(chat)
    return chat_to_json(chat)


@app.delete("/api/chats/{chat_id}")
async def delete_general_chat(chat_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GeneralChatSession).where(GeneralChatSession.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Chat not found")
    await db.delete(chat)
    await db.commit()
    return {"ok": True}


@app.get("/api/chats/{chat_id}/messages")
async def get_general_chat_messages(chat_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GeneralChatMessage)
        .where(GeneralChatMessage.chat_id == chat_id)
        .order_by(GeneralChatMessage.created_at)
    )
    msgs = result.scalars().all()
    return [chat_message_to_json(m) for m in msgs]


@app.get("/api/chat-memory")
async def list_chat_memory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMemory)
        .where(ChatMemory.enabled == True)  # noqa: E712
        .order_by(ChatMemory.updated_at.desc())
    )
    memories = result.scalars().all()
    return [memory_to_json(m) for m in memories]


@app.delete("/api/chat-memory/{memory_id}")
async def delete_chat_memory(memory_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatMemory).where(ChatMemory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(404, "Memory not found")
    await db.delete(memory)
    await db.commit()
    return {"ok": True}


# ─── General chat WebSocket ────────────────────────────────────
# Keep this route before /ws/{project_id}/{session_id}. Both paths have two
# URL segments, so route order matters.

@app.websocket("/ws/chats/{chat_id}")
async def general_chat_websocket(ws: WebSocket, chat_id: str):
    await ws.accept()
    orch = GeneralChatOrchestrator()
    agent_orch = GeneralAgentOrchestrator()

    try:
        while True:
            data = await ws.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue
            _atts = data.get("attachments", []) or []
            att_text = "\n\n".join(f"[file: {a.get('name')}]\n{a.get('text','')}" for a in _atts if a.get("kind") == "text")
            att_images = [a["data_url"] for a in _atts if a.get("kind") == "image" and a.get("data_url")]

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(GeneralChatSession).where(GeneralChatSession.id == chat_id))
                chat = result.scalar_one_or_none()
                if not chat:
                    await ws.send_json({"type": "error", "message": "Chat not found."})
                    continue

                history_result = await db.execute(
                    select(GeneralChatMessage)
                    .where(GeneralChatMessage.chat_id == chat_id)
                    .order_by(GeneralChatMessage.created_at)
                )
                history_msgs = history_result.scalars().all()
                history = [{"role": m.role, "content": m.content} for m in history_msgs]

                memory_rows = []
                if chat.memory_enabled:
                    mem_result = await db.execute(
                        select(ChatMemory)
                        .where(ChatMemory.enabled == True)  # noqa: E712
                        .order_by(ChatMemory.updated_at.desc())
                    )
                    memory_rows = mem_result.scalars().all()

                user_msg = GeneralChatMessage(
                    id=str(uuid.uuid4()),
                    chat_id=chat_id,
                    role="user",
                    content=user_message,
                )
                db.add(user_msg)
                await db.commit()

            async def stream_cb(event: dict):
                await ws.send_json(event)

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(GeneralChatSession).where(GeneralChatSession.id == chat_id))
                chat_row = result.scalar_one_or_none()
                try:
                    sel = await selection_mod.resolve_selection(
                        db,
                        provider_id=chat_row.model_provider_id if chat_row else None,
                        model=chat_row.model if chat_row else None,
                    )
                    resolved = await selection_mod.build_call(db, sel)
                    skills = await select_skills(db, user_message, resolved)
                except LLMError as e:
                    await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                    continue

            skills_block = build_skills_block(skills)
            if skills:
                await ws.send_json({"type": "skills_activated", "names": [s.name for s in skills]})

            try:
                active_orch = agent_orch if bool(chat_row and chat_row.agent_enabled) else orch
                await ws.send_json({
                    "type": "mode",
                    "mode": "agent" if bool(chat_row and chat_row.agent_enabled) else "direct",
                })
                final = await active_orch.process(
                    user_message,
                    history=history,
                    memories=[m.content for m in memory_rows],
                    resolved=resolved,
                    stream_cb=stream_cb,
                    skills_block=skills_block,
                    attachments_text=att_text,
                    attachment_images=att_images,
                    web_enabled=bool(chat_row and chat_row.web_enabled),
                )
            except LLMError as e:
                # Surface the error to the client; do NOT persist it as an assistant message.
                await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                continue
            except Exception:
                await ws.send_json({"type": "error", "message": "Internal error processing request."})
                continue

            chat_title = None
            assistant_id = str(uuid.uuid4())

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(GeneralChatSession).where(GeneralChatSession.id == chat_id))
                chat = result.scalar_one_or_none()
                if not chat:
                    await ws.send_json({"type": "error", "message": "Chat not found after response."})
                    continue

                assistant_msg = GeneralChatMessage(
                    id=assistant_id,
                    chat_id=chat_id,
                    role="assistant",
                    content=final,
                )
                db.add(assistant_msg)

                if chat.title == "New chat":
                    chat.title = auto_title(user_message)
                    chat_title = chat.title

                candidate = memory_candidate(user_message, final) if chat.memory_enabled else None
                if candidate:
                    existing = await db.execute(
                        select(ChatMemory).where(ChatMemory.content == candidate)
                    )
                    if not existing.scalar_one_or_none():
                        memory = ChatMemory(
                            id=str(uuid.uuid4()),
                            memory_type="preference",
                            content=candidate,
                            source_chat_id=chat_id,
                            source_message_id=assistant_id,
                        )
                        db.add(memory)
                        await ws.send_json({"type": "memory_saved", "content": candidate})

                await db.commit()

            await ws.send_json({
                "type": "final",
                "id": assistant_id,
                "content": final,
                "chat_title": chat_title,
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ─── Cowork WebSocket ─────────────────────────────────────────
# Must be registered BEFORE /ws/{project_id}/{session_id} — both are 2-segment
# paths and FastAPI resolves routes in registration order.

@app.websocket("/ws/cowork/{session_id}")
async def cowork_websocket(ws: WebSocket, session_id: str):
    await ws.accept()
    orch = CoworkOrchestrator()
    try:
        while True:
            data = await ws.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue
            _atts = data.get("attachments", []) or []
            att_text = "\n\n".join(f"[file: {a.get('name')}]\n{a.get('text','')}" for a in _atts if a.get("kind") == "text")
            att_images = [a["data_url"] for a in _atts if a.get("kind") == "image" and a.get("data_url")]

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(CoworkSession).where(CoworkSession.id == session_id))
                sess = res.scalar_one_or_none()
                if not sess:
                    await ws.send_json({"type": "error", "message": "Cowork session not found."})
                    continue
                doc_content = sess.doc_content or ""
                hist_res = await db.execute(
                    select(CoworkMessage).where(CoworkMessage.session_id == session_id).order_by(CoworkMessage.created_at)
                )
                history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]
                db.add(CoworkMessage(id=str(uuid.uuid4()), session_id=session_id, role="user", content=user_message))
                await db.commit()
                provider_id = sess.model_provider_id
                model = sess.model

            async with AsyncSessionLocal() as db:
                try:
                    sel = await selection_mod.resolve_selection(db, provider_id=provider_id, model=model)
                    resolved = await selection_mod.build_call(db, sel)
                    skills = await select_skills(db, user_message, resolved)
                except LLMError as e:
                    await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                    continue

            skills_block = build_skills_block(skills)
            if skills:
                await ws.send_json({"type": "skills_activated", "names": [s.name for s in skills]})

            async def stream_cb(event: dict):
                await ws.send_json(event)

            try:
                reply, new_doc = await orch.process(user_message, history, doc_content, resolved, stream_cb=stream_cb, skills_block=skills_block, attachments_text=att_text, attachment_images=att_images)
            except LLMError as e:
                await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                continue
            except Exception as e:
                await ws.send_json({"type": "error", "message": str(e)})
                continue

            assistant_id = str(uuid.uuid4())
            async with AsyncSessionLocal() as db:
                db.add(CoworkMessage(id=assistant_id, session_id=session_id, role="assistant", content=reply))
                if new_doc is not None:
                    res = await db.execute(select(CoworkSession).where(CoworkSession.id == session_id))
                    s2 = res.scalar_one_or_none()
                    if s2:
                        s2.doc_content = new_doc
                await db.commit()

            await ws.send_json({"type": "final", "id": assistant_id, "content": reply})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ─── Code WebSocket chat ──────────────────────────────────────
# Separate Claude Code-style pipeline. It has its own sidebar tab/API/socket,
# but delegates execution to the project agent engine so it can reuse the
# existing file, bash, search, validation, and DeepAgents integrations.

@app.websocket("/ws/code/{code_session_id}")
async def code_websocket(ws: WebSocket, code_session_id: str):
    await ws.accept()

    try:
        while True:
            data = await ws.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue
            _atts = data.get("attachments", []) or []
            att_text = "\n\n".join(f"[file: {a.get('name')}]\n{a.get('text','')}" for a in _atts if a.get("kind") == "text")
            att_images = [a["data_url"] for a in _atts if a.get("kind") == "image" and a.get("data_url")]

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(CodeSession).where(CodeSession.id == code_session_id))
                code_sess = res.scalar_one_or_none()
                if not code_sess:
                    await ws.send_json({"type": "error", "message": "Code workspace not found."})
                    continue

                project_id = code_sess.project_id
                chat_session_id = code_sess.chat_session_id
                db.add(CodeMessage(
                    id=str(uuid.uuid4()),
                    session_id=code_session_id,
                    role="user",
                    content=user_message,
                ))
                db.add(ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=chat_session_id,
                    role="user",
                    content=user_message,
                ))
                await db.commit()

            trace_events = []

            async def stream_cb(event: dict):
                trace_events.append(event)
                await ws.send_json(event)

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(CodeSession).where(CodeSession.id == code_session_id))
                code_sess = res.scalar_one_or_none()
                if not code_sess:
                    await ws.send_json({"type": "error", "message": "Code workspace not found."})
                    continue
                project_id = code_sess.project_id
                chat_session_id = code_sess.chat_session_id
                try:
                    sel = await selection_mod.resolve_selection(
                        db,
                        provider_id=code_sess.model_provider_id,
                        model=code_sess.model,
                    )
                    resolved = await selection_mod.build_call(db, sel)
                    skills = await select_skills(db, user_message, resolved)
                except LLMError as e:
                    await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                    continue
                engine_name = code_sess.engine or "crewai"

            skills_block = build_skills_block(skills)
            if skills:
                await ws.send_json({"type": "skills_activated", "names": [s.name for s in skills]})

            from core.engines.registry import get_engine
            orch = get_engine(engine_name, project_id, chat_session_id, resolved)

            await ws.send_json({"type": "status", "message": "Code agent running in isolated Code workspace…"})

            try:
                final = await orch.process(
                    user_message,
                    stream_cb=stream_cb,
                    skills_block=skills_block,
                    attachments_text=att_text,
                    attachment_images=att_images,
                )
            except LLMError as e:
                await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                continue
            except Exception as e:
                final = f"Error processing code request: {str(e)}"
                await ws.send_json({"type": "error", "message": str(e)})

            assistant_id = str(uuid.uuid4())
            async with AsyncSessionLocal() as db:
                db.add(CodeMessage(
                    id=assistant_id,
                    session_id=code_session_id,
                    role="assistant",
                    content=final,
                    meta={"trace": trace_events},
                ))
                db.add(ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=chat_session_id,
                    role="assistant",
                    content=final,
                    meta={"trace": trace_events},
                ))
                await db.commit()

            await ws.send_json({"type": "final", "id": assistant_id, "content": final, "workspace_updated": True})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ─── Project WebSocket chat ────────────────────────────────────

@app.websocket("/ws/{project_id}/{session_id}")
async def chat_websocket(ws: WebSocket, project_id: str, session_id: str):
    await ws.accept()

    try:
        while True:
            data = await ws.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue
            _atts = data.get("attachments", []) or []
            att_text = "\n\n".join(f"[file: {a.get('name')}]\n{a.get('text','')}" for a in _atts if a.get("kind") == "text")
            att_images = [a["data_url"] for a in _atts if a.get("kind") == "image" and a.get("data_url")]

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ChatSession).where(
                        ChatSession.id == session_id,
                        ChatSession.project_id == project_id,
                    )
                )
                session = result.scalar_one_or_none()
                if not session:
                    await ws.send_json({"type": "error", "message": "Project chat session not found."})
                    continue

                db.add(ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="user",
                    content=user_message,
                ))
                await db.commit()

            trace_events = []

            async def stream_cb(event: dict):
                trace_events.append(event)
                await ws.send_json(event)

            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(ChatSession).where(
                        ChatSession.id == session_id,
                        ChatSession.project_id == project_id,
                    )
                )
                sess_row = res.scalar_one_or_none()
                try:
                    sel = await selection_mod.resolve_selection(
                        db,
                        provider_id=sess_row.model_provider_id if sess_row else None,
                        model=sess_row.model if sess_row else None,
                    )
                    resolved = await selection_mod.build_call(db, sel)
                    skills = await select_skills(db, user_message, resolved)
                except LLMError as e:
                    await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                    continue
                engine_name = sess_row.engine if sess_row else "crewai"

            skills_block = build_skills_block(skills)
            if skills:
                await ws.send_json({"type": "skills_activated", "names": [s.name for s in skills]})

            from core.engines.registry import get_engine
            orch = get_engine(engine_name, project_id, session_id, resolved)

            try:
                final = await orch.process(user_message, stream_cb=stream_cb, skills_block=skills_block, attachments_text=att_text, attachment_images=att_images)
            except LLMError as e:
                await ws.send_json({"type": "error", "code": e.code, "message": e.message})
                continue
            except Exception as e:
                final = f"Error processing request: {str(e)}"
                await ws.send_json({"type": "error", "message": str(e)})

            assistant_id = str(uuid.uuid4())
            async with AsyncSessionLocal() as db:
                db.add(ChatMessage(
                    id=assistant_id,
                    session_id=session_id,
                    role="assistant",
                    content=final,
                    meta={"trace": trace_events},
                ))
                await db.commit()

            await ws.send_json({"type": "final", "id": assistant_id, "content": final})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ─── Health check ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}
