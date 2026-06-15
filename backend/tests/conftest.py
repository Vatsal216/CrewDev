import os

# Must be set before db.models / config are imported anywhere.
os.environ.setdefault("APP_SECRET", "test-app-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from db.models import Base


@pytest_asyncio.fixture
async def db_session():
    """Fresh in-memory SQLite session per test (StaticPool keeps one connection
    so the in-memory DB persists for the duration of the test)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()
