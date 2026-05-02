"""Unit tests for executions API — mocked DB session."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.db import get_db
from api.app.middleware import RequestIDMiddleware
from api.app.models.execution import ExecutionStatus
from api.app.routes.v1.executions import router

_ANALYST_HEADERS = {"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"}
_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}
_SVC_HEADERS = {"X-Feanor-Subject": "worker", "X-Feanor-Roles": "service_account"}


def _make_execution(**kw: object) -> MagicMock:
    now = datetime.now(timezone.utc)
    e = MagicMock()
    e.id = kw.get("id", uuid.uuid4())
    e.workflow_id = kw.get("workflow_id", uuid.uuid4())
    e.status = kw.get("status", ExecutionStatus.pending)
    e.inputs = kw.get("inputs", None)
    e.result_ref = kw.get("result_ref", None)
    e.log_ref = kw.get("log_ref", None)
    e.cancel_requested = kw.get("cancel_requested", False)
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
    exc = _make_execution(created_by="carol")
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


# ---------------------------------------------------------------------------
# PATCH /{id}/status
# ---------------------------------------------------------------------------


def test_status_patch_requires_service_account() -> None:
    exc = _make_execution(status=ExecutionStatus.pending)
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    db.flush = AsyncMock()
    client = _build_app(db)
    resp = client.patch(
        f"/executions/{exc.id}/status",
        json={"status": "running"},
        headers=_ENG_HEADERS,
    )
    assert resp.status_code == 403


def test_status_patch_valid_transition_pending_to_running() -> None:
    exc = _make_execution(status=ExecutionStatus.pending)
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    db.flush = AsyncMock()
    client = _build_app(db)
    resp = client.patch(
        f"/executions/{exc.id}/status",
        json={"status": "running"},
        headers=_SVC_HEADERS,
    )
    assert resp.status_code == 200


def test_status_patch_invalid_transition_returns_409() -> None:
    exc = _make_execution(status=ExecutionStatus.pending)
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.patch(
        f"/executions/{exc.id}/status",
        json={"status": "succeeded"},
        headers=_SVC_HEADERS,
    )
    assert resp.status_code == 409


def test_status_patch_not_found_returns_404() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    client = _build_app(db)
    resp = client.patch(
        f"/executions/{uuid.uuid4()}/status",
        json={"status": "running"},
        headers=_SVC_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /{id}/cancel
# ---------------------------------------------------------------------------


def test_cancel_pending_execution_returns_200() -> None:
    exc = _make_execution(status=ExecutionStatus.pending, created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    db.flush = AsyncMock()
    client = _build_app(db)
    resp = client.post(f"/executions/{exc.id}/cancel", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200


def test_cancel_terminal_execution_returns_409() -> None:
    exc = _make_execution(status=ExecutionStatus.succeeded, created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.post(f"/executions/{exc.id}/cancel", headers=_ANALYST_HEADERS)
    assert resp.status_code == 409
    assert "terminal" in resp.json()["detail"].lower()


def test_analyst_cannot_cancel_other_users_execution() -> None:
    exc = _make_execution(status=ExecutionStatus.pending, created_by="carol")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.post(f"/executions/{exc.id}/cancel", headers=_ANALYST_HEADERS)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /{id}/logs
# ---------------------------------------------------------------------------


def test_logs_returns_204_when_log_ref_is_null() -> None:
    exc = _make_execution(log_ref=None, created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}/logs", headers=_ANALYST_HEADERS)
    assert resp.status_code == 204


def test_logs_analyst_cannot_see_other_users_logs() -> None:
    exc = _make_execution(log_ref="inline:aGVsbG8=", created_by="carol")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}/logs", headers=_ANALYST_HEADERS)
    assert resp.status_code == 403


def test_logs_inline_ref_decodes_correctly() -> None:
    import base64

    log_text = "line1\nline2\nline3"
    encoded = base64.b64encode(log_text.encode()).decode()
    exc = _make_execution(log_ref=f"inline:{encoded}", created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}/logs", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["log"] == log_text


def test_logs_tail_returns_last_n_lines() -> None:
    import base64

    log_text = "\n".join(f"line{i}" for i in range(10))
    encoded = base64.b64encode(log_text.encode()).decode()
    exc = _make_execution(log_ref=f"inline:{encoded}", created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}/logs?tail=3", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200
    lines = resp.json()["data"]["log"].splitlines()
    assert len(lines) == 3
    assert lines[-1] == "line9"


# ---------------------------------------------------------------------------
# GET /{id}/wait
# ---------------------------------------------------------------------------


def test_wait_returns_immediately_when_already_terminal() -> None:
    exc = _make_execution(status=ExecutionStatus.succeeded, created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)
    db.refresh = AsyncMock()
    client = _build_app(db)
    resp = client.get(f"/executions/{exc.id}/wait?timeout=5", headers=_ANALYST_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "succeeded"


def test_wait_returns_408_after_timeout() -> None:
    """Mock the polling loop so it never transitions to terminal."""
    exc = _make_execution(status=ExecutionStatus.running, created_by="alice")
    db = AsyncMock()
    db.get = AsyncMock(return_value=exc)

    async def _fake_refresh(obj: object) -> None:
        pass

    db.refresh = _fake_refresh

    with patch("api.app.routes.v1.executions.asyncio.sleep", new=AsyncMock()):
        client = _build_app(db)
        resp = client.get(f"/executions/{exc.id}/wait?timeout=2", headers=_ANALYST_HEADERS)

    assert resp.status_code == 408
