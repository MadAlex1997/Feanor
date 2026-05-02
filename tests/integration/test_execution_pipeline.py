"""Phase 2 integration tests — execution pipeline end-to-end."""
from __future__ import annotations

import asyncio
import base64
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_template(api_client: AsyncClient, admin_headers: dict, name: str = None) -> str:
    if name is None:
        name = f"serverless_standard_{uuid.uuid4().hex[:6]}"
    resp = await api_client.post(
        "/v1/templates",
        json={"name": name, "type": "serverless", "config": {}},
        headers=admin_headers,
    )
    if resp.status_code == 409:
        # Already exists — look it up
        resp = await api_client.get("/v1/templates", headers=admin_headers)
        templates = resp.json()["data"]
        for t in templates:
            if t["name"] == name:
                return t["id"]
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_workflow(
    api_client: AsyncClient,
    engineer_headers: dict,
    admin_headers: dict,
    slug: str,
    tmpl_id: str,
) -> str:
    resp = await api_client.post(
        "/v1/workflows",
        json={"slug": slug, "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _seed_execution(
    db_session: AsyncSession,
    workflow_id: str,
    created_by: str = "alice",
    status: str = "pending",
    log_ref: str | None = None,
) -> str:
    exec_id = str(uuid.uuid4())
    await db_session.execute(
        text(
            "INSERT INTO executions (id, workflow_id, status, created_by, created_at, log_ref) "
            "VALUES (:id, :wf_id, :status, :created_by, now(), :log_ref)"
        ),
        {
            "id": exec_id,
            "wf_id": workflow_id,
            "status": status,
            "created_by": created_by,
            "log_ref": log_ref,
        },
    )
    await db_session.commit()
    return exec_id


async def _wait_for_status(
    api_client: AsyncClient,
    exec_id: str,
    headers: dict,
    target: str,
    max_secs: int = 30,
) -> dict:
    for _ in range(max_secs // 2):
        resp = await api_client.get(f"/v1/executions/{exec_id}", headers=headers)
        data = resp.json()["data"]
        if data["status"] == target:
            return data
        await asyncio.sleep(2)
    pytest.fail(f"execution {exec_id} did not reach {target!r} within {max_secs}s")


# ---------------------------------------------------------------------------
# Submit and poll
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_submit_workflow_returns_202(
    api_client: AsyncClient,
    engineer_headers: dict,
    admin_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-run-{uuid.uuid4().hex[:6]}", tmpl_id
    )

    resp = await api_client.post(
        f"/v1/workflows/{wf_id}/run",
        json={"inputs": {"key": "value"}},
        headers=engineer_headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["data"]["status"] == "pending"
    assert body["data"]["workflow_id"] == wf_id


@pytest.mark.integration
async def test_submit_run_workflow_not_found(
    api_client: AsyncClient,
    engineer_headers: dict,
) -> None:
    resp = await api_client.post(
        f"/v1/workflows/{uuid.uuid4()}/run",
        json={},
        headers=engineer_headers,
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_submit_creates_pending_execution(
    api_client: AsyncClient,
    engineer_headers: dict,
    admin_headers: dict,
) -> None:
    """Verify submission creates a pending execution with correct metadata."""
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-meta-{uuid.uuid4().hex[:6]}", tmpl_id
    )

    resp = await api_client.post(
        f"/v1/workflows/{wf_id}/run",
        json={"inputs": {"echo": "hello"}},
        headers=engineer_headers,
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["status"] == "pending"
    assert data["workflow_id"] == wf_id
    assert data["inputs"] == {"echo": "hello"}
    assert data["created_by"] == "bob"


# ---------------------------------------------------------------------------
# Status update endpoint (PATCH /executions/{id}/status)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_status_update_valid_transition(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-status-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, status="pending")

    svc_headers = {"X-Feanor-Subject": "worker", "X-Feanor-Roles": "service_account"}
    resp = await api_client.patch(
        f"/v1/executions/{exec_id}/status",
        json={"status": "running"},
        headers=svc_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "running"


@pytest.mark.integration
async def test_status_update_invalid_transition_returns_409(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-invalid-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, status="pending")

    svc_headers = {"X-Feanor-Subject": "worker", "X-Feanor-Roles": "service_account"}
    resp = await api_client.patch(
        f"/v1/executions/{exec_id}/status",
        json={"status": "succeeded"},  # pending → succeeded is invalid
        headers=svc_headers,
    )
    assert resp.status_code == 409


@pytest.mark.integration
async def test_status_update_non_service_account_rejected(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-notsvc-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, status="pending")

    resp = await api_client.patch(
        f"/v1/executions/{exec_id}/status",
        json={"status": "running"},
        headers=engineer_headers,  # engineer, not service_account
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Logs endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_logs_no_log_ref_returns_204(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-logs1-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, status="pending", log_ref=None)

    resp = await api_client.get(f"/v1/executions/{exec_id}/logs", headers=engineer_headers)
    assert resp.status_code == 204


@pytest.mark.integration
async def test_logs_inline_ref_returns_200(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-logs2-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    log_text = "line one\nline two\nline three"
    log_ref = "inline:" + base64.b64encode(log_text.encode()).decode()
    exec_id = await _seed_execution(db_session, wf_id, status="succeeded", log_ref=log_ref)

    resp = await api_client.get(f"/v1/executions/{exec_id}/logs", headers=engineer_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["log"] == log_text


@pytest.mark.integration
async def test_logs_tail_returns_last_n_lines(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-logs3-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    log_text = "\n".join(f"line{i}" for i in range(10))
    log_ref = "inline:" + base64.b64encode(log_text.encode()).decode()
    exec_id = await _seed_execution(db_session, wf_id, status="succeeded", log_ref=log_ref)

    resp = await api_client.get(
        f"/v1/executions/{exec_id}/logs?tail=1", headers=engineer_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["log"] == "line9"


@pytest.mark.integration
async def test_logs_analyst_cannot_see_other_users_logs(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    analyst_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-logs4-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    # Seed execution owned by "bob" (engineer subject), not "alice" (analyst subject)
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="succeeded",
                                     log_ref="inline:aGVsbG8=")

    resp = await api_client.get(f"/v1/executions/{exec_id}/logs", headers=analyst_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cancel endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_cancel_pending_execution(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-cancel1-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="pending")

    resp = await api_client.post(f"/v1/executions/{exec_id}/cancel", headers=engineer_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "cancelled"
    assert data["ended_at"] is not None


@pytest.mark.integration
async def test_cancel_terminal_execution_returns_409(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-cancel2-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="succeeded")

    resp = await api_client.post(f"/v1/executions/{exec_id}/cancel", headers=engineer_headers)
    assert resp.status_code == 409
    assert "terminal" in resp.json()["detail"].lower()


@pytest.mark.integration
async def test_analyst_cannot_cancel_other_users_execution(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    analyst_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-cancel3-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="pending")

    # analyst_headers subject is "alice", execution owned by "bob"
    resp = await api_client.post(f"/v1/executions/{exec_id}/cancel", headers=analyst_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Wait endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_wait_returns_immediately_for_terminal_execution(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-wait1-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="succeeded")

    resp = await api_client.get(
        f"/v1/executions/{exec_id}/wait?timeout=5", headers=engineer_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "succeeded"


@pytest.mark.integration
async def test_wait_returns_408_for_long_running_execution(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-wait2-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    # Seed a running execution that will never transition on its own
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="running")

    resp = await api_client.get(
        f"/v1/executions/{exec_id}/wait?timeout=3", headers=engineer_headers, timeout=10.0
    )
    assert resp.status_code == 408


# ---------------------------------------------------------------------------
# Analyst visibility — logs and cancel
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_analyst_can_access_own_execution_logs(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    analyst_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-own-logs-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    log_ref = "inline:" + base64.b64encode(b"my log").decode()
    # analyst subject is "alice"
    exec_id = await _seed_execution(
        db_session, wf_id, created_by="alice", status="succeeded", log_ref=log_ref
    )

    resp = await api_client.get(f"/v1/executions/{exec_id}/logs", headers=analyst_headers)
    assert resp.status_code == 200


@pytest.mark.integration
async def test_analyst_can_cancel_own_execution(
    api_client: AsyncClient,
    admin_headers: dict,
    engineer_headers: dict,
    analyst_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _create_template(api_client, admin_headers)
    wf_id = await _create_workflow(
        api_client, engineer_headers, admin_headers, f"test-own-cancel-{uuid.uuid4().hex[:6]}", tmpl_id
    )
    exec_id = await _seed_execution(db_session, wf_id, created_by="alice", status="pending")

    resp = await api_client.post(f"/v1/executions/{exec_id}/cancel", headers=analyst_headers)
    assert resp.status_code == 200
