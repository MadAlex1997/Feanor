"""Unit tests for workflows route — mocked DB session."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from api.app.db import get_db
from api.app.middleware import RequestIDMiddleware
from api.app.routes.v1.workflows import router

_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}
_ANALYST_HEADERS = {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}


def _make_template(**kw: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    t = MagicMock()
    t.id = kw.get("id", uuid.uuid4())
    t.name = kw.get("name", "serverless_standard")
    t.type = kw.get("type", "serverless")
    t.config = kw.get("config", None)
    t.created_at = now
    t.updated_at = now
    return t


def _make_workflow(**kw: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    w = MagicMock()
    w.id = kw.get("id", uuid.uuid4())
    w.slug = kw.get("slug", "my-etl")
    w.version = kw.get("version", "v1")
    w.definition = kw.get("definition", None)
    w.execution_template_id = kw.get("execution_template_id", uuid.uuid4())
    w.template = kw.get("template", None)
    w.created_at = kw.get("created_at", now)
    w.updated_at = kw.get("updated_at", now)
    return w


def _build_app(db_mock: AsyncMock) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_mock
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------


def test_create_workflow_returns_201() -> None:
    tmpl = _make_template()
    wf = _make_workflow(execution_template_id=tmpl.id)
    db = AsyncMock()
    db.get = AsyncMock(return_value=tmpl)
    db.flush = AsyncMock()

    async def fake_refresh(obj):
        obj.id = wf.id
        obj.created_at = wf.created_at
        obj.updated_at = wf.updated_at

    db.refresh = AsyncMock(side_effect=fake_refresh)

    client = _build_app(db)
    resp = client.post(
        "/workflows",
        json={"slug": "my-etl", "version": "v1", "execution_template_id": str(tmpl.id)},
        headers=_ENG_HEADERS,
    )
    assert resp.status_code == 201


def test_create_workflow_bad_template_returns_422() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)  # template not found
    client = _build_app(db)
    resp = client.post(
        "/workflows",
        json={"slug": "x", "version": "v1", "execution_template_id": str(uuid.uuid4())},
        headers=_ENG_HEADERS,
    )
    assert resp.status_code == 422


def test_create_workflow_analyst_forbidden() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.post(
        "/workflows",
        json={"slug": "x", "version": "v1", "execution_template_id": str(uuid.uuid4())},
        headers=_ANALYST_HEADERS,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------


def test_get_workflow_404() -> None:
    db = AsyncMock()

    async def fake_execute(stmt):
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        return r

    db.execute = AsyncMock(side_effect=fake_execute)
    client = _build_app(db)
    resp = client.get(f"/workflows/{uuid.uuid4()}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_delete_workflow_non_admin_forbidden() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.delete(f"/workflows/{uuid.uuid4()}", headers=_ENG_HEADERS)
    assert resp.status_code == 403


def test_delete_workflow_not_found() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.delete(f"/workflows/{uuid.uuid4()}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 404


def test_delete_workflow_fk_violation_returns_409() -> None:
    wf = _make_workflow()
    db = AsyncMock()
    db.get = AsyncMock(return_value=wf)
    db.delete = AsyncMock()
    # Simulate FK violation on flush
    fake_orig = Exception("foreign key constraint")
    db.flush = AsyncMock(side_effect=IntegrityError("stmt", {}, fake_orig))
    db.rollback = AsyncMock()
    client = _build_app(db)
    resp = client.delete(f"/workflows/{wf.id}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 409
