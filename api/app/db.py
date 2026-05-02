"""Async database engine, session factory, and FastAPI dependency."""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _build_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://feanor:changeme@localhost:5432/feanor",
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_echo = os.environ.get("LOG_LEVEL", "").upper() == "DEBUG"

engine: AsyncEngine = create_async_engine(_build_url(), echo=_echo)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
