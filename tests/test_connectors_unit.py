"""Unit tests for connectors API — mocked DB session."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.db import get_db
from api.app.middleware import RequestIDMiddleware
from api.app.routes.v1.connectors import _decode_config, _encode_config, router

_ANALYST_HEADERS = {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}
_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}


def _make_connector(**kw: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    c = MagicMock()
    c.id = kw.get("id", uuid.uuid4())
    c.name = kw.get("name", "prod-pg")
    c.type = kw.get("type", "postgresql")
    c.owner = kw.get("owner", "bob")
    raw_config = kw.get("config", {"host": "db.example.com"})
    c.config_encrypted = json.dumps(raw_config).encode() if raw_config else None
    c.created_at = now
    c.updated_at = now
    return c


def _build_app(db_mock: AsyncMock) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_mock
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# encode/decode helpers
# ---------------------------------------------------------------------------


def test_encode_decode_roundtrip() -> None:
    cfg = {"host": "db.example.com", "port": 5432}
    assert _decode_config(_encode_config(cfg)) == cfg


def test_encode_none_returns_none() -> None:
    assert _encode_config(None) is None


def test_decode_none_returns_none() -> None:
    assert _decode_config(None) is None


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------


def test_create_connector_analyst_forbidden() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.post(
        "/connectors",
        json={"name": "x", "type": "postgresql"},
        headers=_ANALYST_HEADERS,
    )
    assert resp.status_code == 403


def test_create_connector_engineer_returns_201() -> None:
    conn = _make_connector()
    db = AsyncMock()
    db.flush = AsyncMock()

    async def fake_refresh(obj):
        obj.id = conn.id
        obj.created_at = conn.created_at
        obj.updated_at = conn.updated_at
        obj.config_encrypted = conn.config_encrypted

    db.refresh = AsyncMock(side_effect=fake_refresh)
    client = _build_app(db)
    resp = client.post(
        "/connectors",
        json={"name": "prod-pg", "type": "postgresql", "config": {"host": "db.example.com"}},
        headers=_ENG_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["owner"] == "bob"
    assert "config_encrypted" not in data


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------


def test_get_connector_not_found() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.get(f"/connectors/{uuid.uuid4()}", headers=_ENG_HEADERS)
    assert resp.status_code == 404


def test_get_connector_config_decoded() -> None:
    conn = _make_connector(config={"host": "db"})
    db = AsyncMock()
    db.get = AsyncMock(return_value=conn)
    client = _build_app(db)
    resp = client.get(f"/connectors/{conn.id}", headers=_ENG_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["config"]["host"] == "db"


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_delete_connector_non_admin_forbidden() -> None:
    db = AsyncMock()
    client = _build_app(db)
    resp = client.delete(f"/connectors/{uuid.uuid4()}", headers=_ENG_HEADERS)
    assert resp.status_code == 403
