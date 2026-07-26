"""Async SQLAlchemy engine + session factory.

The database stores every ticket the service has created or discovered, so the
service — not GitHub — is the source of truth a UI reads from. That keeps the UI
fast, lets the poller de-dup, and means the "new issues" feed works even when
GitHub is rate-limited or unreachable.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create tables on startup. For a demo service plain create_all is enough;
    a production deployment would swap this for Alembic migrations."""
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
