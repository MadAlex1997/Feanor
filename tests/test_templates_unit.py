"""Unit tests for templates API — mocked DB session."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from api.app.db import get_db
from api.app.middleware import RequestIDMiddleware
from api.app.routes.v1.templates import router

_ANALYST_HEADERS = {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}
_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}


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


def _build_app(db_mock: AsyncMock) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_mock
    return TestClient(app, raise_server_exceptions=False)


def test_get_template_not_found() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.get(f"/templates/{uuid.uuid4()}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 404


def test_get_template_found() -> None:
    tmpl = _make_template()
    db = AsyncMock()
    db.get = AsyncMock(return_value=tmpl)
    client = _build_app(db)
    resp = client.get(f"/templates/{tmpl.id}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "serverless_standard"


def test_create_template_non_admin_returns_403() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.post(
        "/templates",
        json={"name": "custom", "type": "serverless"},
        headers=_ENG_HEADERS,
    )
    assert resp.status_code == 403


def test_create_template_admin_returns_201() -> None:
    tmpl = _make_template(name="my-custom")
    db = AsyncMock()
    db.flush = AsyncMock()

    async def fake_refresh(obj):
        obj.id = tmpl.id
        obj.created_at = tmpl.created_at
        obj.updated_at = tmpl.updated_at

    db.refresh = AsyncMock(side_effect=fake_refresh)
    client = _build_app(db)
    resp = client.post(
        "/templates",
        json={"name": "my-custom", "type": "serverless"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 201


def test_create_template_duplicate_name_returns_409() -> None:
    db = AsyncMock()
    db.flush = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("unique constraint")))
    db.rollback = AsyncMock()
    client = _build_app(db)
    resp = client.post(
        "/templates",
        json={"name": "dupe", "type": "serverless"},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 409
