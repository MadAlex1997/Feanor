"""Unit tests for api.app.db.get_db dependency."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.app.db import get_db


def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _make_session_cm(session: AsyncMock) -> MagicMock:
    """Return a context-manager mock that yields the given session."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_get_db_commits_on_success() -> None:
    session = _make_mock_session()
    with patch("api.app.db.AsyncSessionLocal", return_value=_make_session_cm(session)):
        gen = get_db()
        yielded = await gen.__anext__()
        assert yielded is session
        # Signal successful exit (no exception)
        try:
            await gen.asend(None)
        except StopAsyncIteration:
            pass
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_rollback_on_exception() -> None:
    session = _make_mock_session()
    with patch("api.app.db.AsyncSessionLocal", return_value=_make_session_cm(session)):
        gen = get_db()
        await gen.__anext__()
        with pytest.raises(ValueError, match="boom"):
            await gen.athrow(ValueError("boom"))
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_closes_session_on_exception() -> None:
    """Session context manager __aexit__ must be called even when an exception is raised."""
    session = _make_mock_session()
    cm = _make_session_cm(session)
    with patch("api.app.db.AsyncSessionLocal", return_value=cm):
        gen = get_db()
        await gen.__anext__()
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("fail"))
    # __aexit__ on the session CM must have been called (closes the session)
    cm.__aexit__.assert_awaited_once()
