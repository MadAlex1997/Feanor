"""Shared test fixtures for integration tests."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient as HttpxAsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from api.app.db import get_db
from api.app.main import create_app

# ---------------------------------------------------------------------------
# Session-scoped PostgreSQL container + migrated schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_url():
    container = PostgresContainer(
        image="postgres:16",
        dbname="feanor_test",
        username="feanor",
        password="test",
    )
    container.start()
    raw_url = container.get_connection_url()
    # Convert psycopg2 URL to asyncpg
    url = raw_url.replace("+psycopg2", "+asyncpg").replace("postgresql://", "postgresql+asyncpg://", 1)
    if "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": "."}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        container.stop()
        raise RuntimeError(f"alembic upgrade failed:\n{result.stdout}\n{result.stderr}")

    yield url
    container.stop()


@pytest_asyncio.fixture(scope="session")
async def test_engine(pg_url: str):
    engine = create_async_engine(pg_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Per-test async session (no automatic rollback — integration tests accumulate state)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI test client wired to the test DB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def api_client(test_session_factory) -> AsyncGenerator[HttpxAsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Redirect AsyncSessionLocal used by background tasks (dispatcher) to the test DB.
    import api.app.routes.v1.workflows as _wf_module
    import api.app.dispatch as _dispatch_module
    _wf_module.AsyncSessionLocal = test_session_factory  # type: ignore[attr-defined]
    _dispatch_module  # imported but AsyncSessionLocal not used directly there

    async with HttpxAsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Auth header fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def analyst_headers() -> dict:
    return {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}


@pytest.fixture(scope="session")
def engineer_headers() -> dict:
    return {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}


@pytest.fixture(scope="session")
def admin_headers() -> dict:
    return {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}
