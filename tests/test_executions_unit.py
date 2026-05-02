"""Unit tests for executions read API — mocked DB session."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.db import get_db
from api.app.middleware import RequestIDMiddleware
from api.app.routes.v1.executions import router

_ANALYST_HEADERS = {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}
_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}


def _make_execution(**kw: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    e = MagicMock()
    e.id = kw.get("id", uuid.uuid4())
    e.workflow_id = kw.get("workflow_id", uuid.uuid4())
    e.status = kw.get("status", "pending")
    e.inputs = kw.get("inputs", None)
    e.result_ref = kw.get("result_ref", None)
    e.log_ref = kw.get("log_ref", None)
    e.started_at = kw.get("started_at", None)
    e.ended_at = kw.get("ended_at", None)
    e.created_at = kw.get("created_at", now)
    e.created_by = kw.get("created_by", "alice")
    return e


def _build_app(db_mock: AsyncMock) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_mock
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------


def test_get_execution_not_found() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.get(f"/executions/{uuid.uuid4()}", headers=_ENG_HEADERS)
    assert resp.status_code == 404


def test_get_execution_returns_200_for_engineer() -> None:
    exc = _make_execution(created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}", headers=_ENG_HEADERS)
    assert resp.status_code == 200


def test_analyst_cannot_see_other_users_execution() -> None:
    exc = _make_execution(created_by="carol")  # different user
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 403


def test_analyst_can_see_own_execution() -> None:
    exc = _make_execution(created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET / (list)
# ---------------------------------------------------------------------------


def _fake_execute_empty():
    async def _inner(stmt):
        r = MagicMock()
        r.scalars.return_value = iter([])
        r.scalar_one.return_value = 0
        return r

    return _inner


def test_list_executions_requires_auth() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.get("/executions")
    assert resp.status_code == 401


def test_list_executions_invalid_status_returns_400() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=_fake_execute_empty())
    client = _build_app(db)
    resp = client.get("/executions?status=bogus", headers=_ANALYST_HEADERS)
    assert resp.status_code == 400
