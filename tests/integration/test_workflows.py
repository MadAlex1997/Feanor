"""Integration tests for /v1/workflows."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.integration


async def _get_template_id(api_client: AsyncClient, admin_headers: dict) -> str:
    resp = await api_client.get("/v1/templates", headers=admin_headers)
    templates = resp.json()["data"]
    assert templates, "no seeded templates found"
    return templates[0]["id"]


async def test_post_creates_workflow(api_client: AsyncClient, engineer_headers: dict, admin_headers: dict) -> None:
    tmpl_id = await _get_template_id(api_client, admin_headers)
    resp = await api_client.post(
        "/v1/workflows",
        json={"slug": "my-etl", "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["slug"] == "my-etl"
    assert data["version"] == "v1"


async def test_duplicate_slug_version_returns_409(api_client: AsyncClient, engineer_headers: dict, admin_headers: dict) -> None:
    tmpl_id = await _get_template_id(api_client, admin_headers)
    await api_client.post(
        "/v1/workflows",
        json={"slug": "dup-wf", "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    resp = await api_client.post(
        "/v1/workflows",
        json={"slug": "dup-wf", "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    assert resp.status_code == 409


async def test_bad_template_id_returns_422(api_client: AsyncClient, engineer_headers: dict) -> None:
    resp = await api_client.post(
        "/v1/workflows",
        json={"slug": "x", "version": "v1", "execution_template_id": str(uuid.uuid4())},
        headers=engineer_headers,
    )
    assert resp.status_code == 422


async def test_get_by_id_includes_template(api_client: AsyncClient, engineer_headers: dict, admin_headers: dict) -> None:
    tmpl_id = await _get_template_id(api_client, admin_headers)
    create_resp = await api_client.post(
        "/v1/workflows",
        json={"slug": "with-tmpl", "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    wf_id = create_resp.json()["data"]["id"]
    resp = await api_client.get(f"/v1/workflows/{wf_id}", headers=engineer_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["template"] is not None
    assert data["template"]["id"] == tmpl_id


async def test_delete_blocked_by_execution_returns_409(
    api_client: AsyncClient,
    engineer_headers: dict,
    admin_headers: dict,
    db_session: AsyncSession,
) -> None:
    tmpl_id = await _get_template_id(api_client, admin_headers)
    create_resp = await api_client.post(
        "/v1/workflows",
        json={"slug": "del-blocked", "version": "v1", "execution_template_id": tmpl_id},
        headers=engineer_headers,
    )
    wf_id = create_resp.json()["data"]["id"]

    # Directly insert an execution referencing this workflow
    await db_session.execute(
        text(
            "INSERT INTO executions (id, workflow_id, status, created_by, created_at) "
            "VALUES (:id, :wf_id, 'pending', 'test', now())"
        ),
        {"id": str(uuid.uuid4()), "wf_id": wf_id},
    )
    await db_session.commit()

    resp = await api_client.delete(f"/v1/workflows/{wf_id}", headers=admin_headers)
    assert resp.status_code == 409
