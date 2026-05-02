"""Integration tests for /v1/executions."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.integration


async def _seed_execution(
    db_session: AsyncSession,
    workflow_id: str,
    created_by: str = "alice",
    status: str = "pending",
) -> str:
    exec_id = str(uuid.uuid4())
    await db_session.execute(
        text(
            "INSERT INTO executions (id, workflow_id, status, created_by, created_at) "
            "VALUES (:id, :wf_id, :status, :created_by, now())"
        ),
        {"id": exec_id, "wf_id": workflow_id, "status": status, "created_by": created_by},
    )
    await db_session.commit()
    return exec_id


async def _create_workflow(api_client: AsyncClient, engineer_headers: dict, admin_headers: dict, slug: str) -> str:
    tmpl_resp = await api_client.get("/v1/templates", headers=admin_headers)
    tmpl_id = tmpl_resp.json()["data"][0]["id"]
    wf_resp = await api_client.post(
        "/v1/workflows",
        json={"slug": slug, "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    return wf_resp.json()["data"]["id"]


async def test_list_empty_initially(api_client: AsyncClient, engineer_headers: dict) -> None:
    resp = await api_client.get("/v1/executions", headers=engineer_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_list_returns_seeded_records(
    api_client: AsyncClient,
    engineer_headers: dict,
    admin_headers: dict,
    db_session: AsyncSession,
) -> None:
    wf_id = await _create_workflow(api_client, engineer_headers, admin_headers, "exec-list-wf")
    exec_id = await _seed_execution(db_session, wf_id, created_by="bob", status="succeeded")
    resp = await api_client.get(f"/v1/executions?workflow_id={wf_id}", headers=engineer_headers)
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()["data"]]
    assert exec_id in ids


async def test_status_filter_returns_only_matching(
    api_client: AsyncClient,
    engineer_headers: dict,
    admin_headers: dict,
    db_session: AsyncSession,
) -> None:
    wf_id = await _create_workflow(api_client, engineer_headers, admin_headers, "exec-filter-wf")
    await _seed_execution(db_session, wf_id, status="succeeded")
    await _seed_execution(db_session, wf_id, status="failed")

    resp = await api_client.get(f"/v1/executions?status=succeeded&workflow_id={wf_id}", headers=engineer_headers)
    assert resp.status_code == 200
    for e in resp.json()["data"]:
        assert e["status"] == "succeeded"


async def test_analyst_visibility_scoping(
    api_client: AsyncClient,
    analyst_headers: dict,
    engineer_headers: dict,
    admin_headers: dict,
    db_session: AsyncSession,
) -> None:
    wf_id = await _create_workflow(api_client, engineer_headers, admin_headers, "vis-scope-wf")
    alice_exec = await _seed_execution(db_session, wf_id, created_by="alice")
    carol_exec = await _seed_execution(db_session, wf_id, created_by="carol")

    resp = await api_client.get(f"/v1/executions?workflow_id={wf_id}", headers=analyst_headers)
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()["data"]]
    assert alice_exec in ids
    assert carol_exec not in ids
