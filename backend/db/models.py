from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Boolean, Integer, text, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import settings


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workspace_path: Mapped[str] = mapped_column(String(512))
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    index_status: Mapped[str] = mapped_column(String(50), default="pending")
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    harness_state: Mapped[Optional["HarnessState"]] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model_provider_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    engine: Mapped[str] = mapped_column(String(20), default="crewai")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # agent traces, sources
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class GeneralChatSession(Base):
    __tablename__ = "general_chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    web_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(20), default="direct")  # direct | agent
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model_provider_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[list["GeneralChatMessage"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="GeneralChatMessage.created_at",
    )


class GeneralChatMessage(Base):
    __tablename__ = "general_chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(36), ForeignKey("general_chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parent_message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chat: Mapped["GeneralChatSession"] = relationship(back_populates="messages")


class ChatMemory(Base):
    __tablename__ = "chat_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    memory_type: Mapped[str] = mapped_column(String(50), default="preference")
    content: Mapped[str] = mapped_column(Text)
    source_chat_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=80)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HarnessState(Base):
    __tablename__ = "harness_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), unique=True)
    goals: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    architecture: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decisions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    active_tasks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    tech_stack: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="harness_state")


class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))  # anthropic|openai|azure|ollama
    label: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    config_encrypted: Mapped[str] = mapped_column(Text)  # Fernet token of the config JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CoworkSession(Base):
    __tablename__ = "cowork_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="New workspace")
    doc_content: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model_provider_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[list["CoworkMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="CoworkMessage.created_at"
    )


class CoworkMessage(Base):
    __tablename__ = "cowork_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("cowork_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CoworkSession"] = relationship(back_populates="messages")


class CodeSession(Base):
    __tablename__ = "code_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="New code workspace")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    chat_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"))
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model_provider_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    engine: Mapped[str] = mapped_column(String(20), default="crewai")
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[list["CodeMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="CodeMessage.created_at"
    )


class CodeMessage(Base):
    __tablename__ = "code_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CodeSession"] = relationship(back_populates="messages")


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_general_chat_sessions(conn)


async def _migrate_general_chat_sessions(conn):
    """Small additive migration for older local DBs.

    create_all() creates new tables, but it does not add columns to an existing
    SQLite/Postgres database. Keep this lightweight so developer machines do not
    break when the General Chat Agent toggle is introduced.
    """
    def _columns(sync_conn):
        inspector = inspect(sync_conn)
        try:
            return {col["name"] for col in inspector.get_columns("general_chat_sessions")}
        except Exception:
            return set()

    cols = await conn.run_sync(_columns)
    dialect = getattr(getattr(conn, "dialect", None), "name", "") or getattr(conn.engine.dialect, "name", "")
    false_default = "false" if dialect.startswith("postgres") else "0"

    if "agent_enabled" not in cols:
        await conn.execute(text(
            f"ALTER TABLE general_chat_sessions ADD COLUMN agent_enabled BOOLEAN NOT NULL DEFAULT {false_default}"
        ))
    if "mode" not in cols:
        await conn.execute(text(
            "ALTER TABLE general_chat_sessions ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'direct'"
        ))
