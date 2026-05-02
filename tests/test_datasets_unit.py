"""Unit tests for the datasets route — mocked DB session."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.db import get_db
from api.app.middleware import RequestIDMiddleware
from api.app.routes.v1.datasets import router

# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------

_ANALYST_HEADERS = {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}
_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}


def _make_dataset(**overrides: object):
    now = datetime.now(timezone.utc)
    d = MagicMock()
    d.id = overrides.get("id", uuid.uuid4())
    d.name = overrides.get("name", "test-ds")
    d.source_ref = overrides.get("source_ref", "s3://bucket/path/")
    d.schema_hints = overrides.get("schema_hints", None)
    d.created_by = overrides.get("created_by", "alice")
    d.lineage_refs = overrides.get("lineage_refs", None)
    d.created_at = overrides.get("created_at", now)
    d.updated_at = overrides.get("updated_at", now)
    return d


def _build_app(db_mock: AsyncMock) -> TestClient:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = lambda: db_mock
    return TestClient(test_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /datasets
# ---------------------------------------------------------------------------


def test_create_dataset_returns_201() -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    ds = _make_dataset()
    db.refresh = AsyncMock(return_value=ds)
    db.add = MagicMock()

    async def fake_refresh(obj):
        obj.id = ds.id
        obj.created_at = ds.created_at
        obj.updated_at = ds.updated_at

    db.refresh.side_effect = fake_refresh

    client = _build_app(db)
    resp = client.post(
        "/datasets",
        json={"name": "my-ds", "source_ref": "s3://b/p/"},
        headers=_ANALYST_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "my-ds"
    assert data["created_by"] == "alice"


def test_create_dataset_forbidden_without_auth() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.post("/datasets", json={"name": "x", "source_ref": "s3://b/"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /datasets/{id}
# ---------------------------------------------------------------------------


def test_get_dataset_returns_404_when_missing() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.get(f"/datasets/{uuid.uuid4()}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 404


def test_get_dataset_returns_200_when_found() -> None:
    ds = _make_dataset()
    db = AsyncMock()
    db.get = AsyncMock(return_value=ds)
    client = _build_app(db)
    resp = client.get(f"/datasets/{ds.id}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == str(ds.id)


# ---------------------------------------------------------------------------
# DELETE /datasets/{id}
# ---------------------------------------------------------------------------


def test_delete_requires_admin() -> None:
    db = AsyncMock()
    ds = _make_dataset()
    db.get = AsyncMock(return_value=ds)
    client = _build_app(db)
    resp = client.delete(f"/datasets/{ds.id}", headers=_ANALYST_HEADERS)
    assert resp.status_code == 403


def test_delete_returns_204() -> None:
    ds = _make_dataset()
    db = AsyncMock()
    db.get = AsyncMock(return_value=ds)
    db.delete = AsyncMock()
    client = _build_app(db)
    resp = client.delete(f"/datasets/{ds.id}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 204


def test_delete_returns_404_when_missing() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.delete(f"/datasets/{uuid.uuid4()}", headers=_ADMIN_HEADERS)
    assert resp.status_code == 404
