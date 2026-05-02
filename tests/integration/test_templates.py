"""Integration tests for /v1/templates."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


async def test_list_returns_four_seeded_templates(api_client: AsyncClient, analyst_headers: dict) -> None:
    resp = await api_client.get("/v1/templates", headers=analyst_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    names = {t["name"] for t in data}
    assert "serverless_standard" in names
    assert "container_job_standard" in names
    assert "container_job_gpu" in names
    assert "distributed_spark_medium" in names


async def test_get_template_by_id(api_client: AsyncClient, analyst_headers: dict) -> None:
    list_resp = await api_client.get("/v1/templates", headers=analyst_headers)
    tmpl_id = list_resp.json()["data"][0]["id"]
    resp = await api_client.get(f"/v1/templates/{tmpl_id}", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == tmpl_id


async def test_get_template_not_found(api_client: AsyncClient, analyst_headers: dict) -> None:
    resp = await api_client.get(f"/v1/templates/{uuid.uuid4()}", headers=analyst_headers)
    assert resp.status_code == 404


async def test_post_template_admin_only(api_client: AsyncClient, analyst_headers: dict, admin_headers: dict) -> None:
    # non-admin returns 403
    resp_analyst = await api_client.post(
        "/v1/templates",
        json={"name": "custom-tmpl", "type": "serverless"},
        headers=analyst_headers,
    )
    assert resp_analyst.status_code == 403

    # admin succeeds
    resp_admin = await api_client.post(
        "/v1/templates",
        json={"name": "custom-tmpl-admin", "type": "serverless", "config": {"key": "val"}},
        headers=admin_headers,
    )
    assert resp_admin.status_code == 201
    assert resp_admin.json()["data"]["name"] == "custom-tmpl-admin"


async def test_type_filter(api_client: AsyncClient, analyst_headers: dict) -> None:
    resp = await api_client.get("/v1/templates?type=serverless", headers=analyst_headers)
    assert resp.status_code == 200
    for t in resp.json()["data"]:
        assert t["type"] == "serverless"
