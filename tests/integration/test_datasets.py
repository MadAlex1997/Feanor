"""Integration tests for /v1/datasets."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


async def test_post_creates_dataset(api_client: AsyncClient, analyst_headers: dict) -> None:
    resp = await api_client.post(
        "/v1/datasets",
        json={"name": "sales-q3", "source_ref": "s3://bucket/sales/q3/"},
        headers=analyst_headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "sales-q3"
    assert data["created_by"] == "alice"
    assert data["id"] is not None


async def test_get_list_returns_datasets(api_client: AsyncClient, analyst_headers: dict) -> None:
    # Create a dataset first
    await api_client.post(
        "/v1/datasets",
        json={"name": "list-test", "source_ref": "s3://bucket/list/"},
        headers=analyst_headers,
    )
    resp = await api_client.get("/v1/datasets", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    assert body["meta"]["limit"] == 20


async def test_get_list_pagination_cursor(api_client: AsyncClient, analyst_headers: dict) -> None:
    # Create 3 datasets
    for i in range(3):
        await api_client.post(
            "/v1/datasets",
            json={"name": f"cursor-ds-{i}", "source_ref": f"s3://b/{i}/"},
            headers=analyst_headers,
        )
    # Fetch with limit=2
    resp = await api_client.get("/v1/datasets?limit=2", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    # cursor may or may not be set depending on total count; just check structure
    assert "cursor" in body["meta"]


async def test_get_by_id_returns_dataset(api_client: AsyncClient, analyst_headers: dict) -> None:
    create_resp = await api_client.post(
        "/v1/datasets",
        json={"name": "getbyid", "source_ref": "s3://b/"},
        headers=analyst_headers,
    )
    ds_id = create_resp.json()["data"]["id"]
    resp = await api_client.get(f"/v1/datasets/{ds_id}", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == ds_id


async def test_get_by_id_returns_404(api_client: AsyncClient, analyst_headers: dict) -> None:
    resp = await api_client.get(f"/v1/datasets/{uuid.uuid4()}", headers=analyst_headers)
    assert resp.status_code == 404


async def test_patch_updates_allowed_fields(api_client: AsyncClient, analyst_headers: dict) -> None:
    create_resp = await api_client.post(
        "/v1/datasets",
        json={"name": "original", "source_ref": "s3://b/"},
        headers=analyst_headers,
    )
    ds_id = create_resp.json()["data"]["id"]
    patch_resp = await api_client.patch(
        f"/v1/datasets/{ds_id}",
        json={"name": "updated"},
        headers=analyst_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["name"] == "updated"
    # source_ref must not change
    assert patch_resp.json()["data"]["source_ref"] == "s3://b/"


async def test_delete_returns_204(api_client: AsyncClient, analyst_headers: dict, admin_headers: dict) -> None:
    create_resp = await api_client.post(
        "/v1/datasets",
        json={"name": "to-delete", "source_ref": "s3://b/"},
        headers=analyst_headers,
    )
    ds_id = create_resp.json()["data"]["id"]
    del_resp = await api_client.delete(f"/v1/datasets/{ds_id}", headers=admin_headers)
    assert del_resp.status_code == 204
    # Second delete returns 404
    del_resp2 = await api_client.delete(f"/v1/datasets/{ds_id}", headers=admin_headers)
    assert del_resp2.status_code == 404


async def test_delete_non_admin_returns_403(api_client: AsyncClient, analyst_headers: dict) -> None:
    create_resp = await api_client.post(
        "/v1/datasets",
        json={"name": "no-del", "source_ref": "s3://b/"},
        headers=analyst_headers,
    )
    ds_id = create_resp.json()["data"]["id"]
    resp = await api_client.delete(f"/v1/datasets/{ds_id}", headers=analyst_headers)
    assert resp.status_code == 403
