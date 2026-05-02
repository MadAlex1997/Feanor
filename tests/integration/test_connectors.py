"""Integration tests for /v1/connectors."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


async def test_post_connector_analyst_forbidden(api_client: AsyncClient, analyst_headers: dict) -> None:
    resp = await api_client.post(
        "/v1/connectors",
        json={"name": "my-pg", "type": "postgresql"},
        headers=analyst_headers,
    )
    assert resp.status_code == 403


async def test_post_connector_engineer_returns_201(api_client: AsyncClient, engineer_headers: dict) -> None:
    resp = await api_client.post(
        "/v1/connectors",
        json={"name": "eng-pg", "type": "postgresql", "config": {"host": "db.example.com", "port": 5432}},
        headers=engineer_headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["owner"] == "bob"
    # config round-trips correctly
    assert data["config"]["host"] == "db.example.com"
    # config_encrypted must NOT appear in response
    assert "config_encrypted" not in data


async def test_get_connector_by_id(api_client: AsyncClient, engineer_headers: dict) -> None:
    create_resp = await api_client.post(
        "/v1/connectors",
        json={"name": "get-pg", "type": "postgresql"},
        headers=engineer_headers,
    )
    conn_id = create_resp.json()["data"]["id"]
    resp = await api_client.get(f"/v1/connectors/{conn_id}", headers=engineer_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == conn_id


async def test_get_connector_not_found(api_client: AsyncClient, engineer_headers: dict) -> None:
    resp = await api_client.get(f"/v1/connectors/{uuid.uuid4()}", headers=engineer_headers)
    assert resp.status_code == 404


async def test_list_type_filter(api_client: AsyncClient, engineer_headers: dict) -> None:
    await api_client.post(
        "/v1/connectors",
        json={"name": "s3-conn", "type": "s3"},
        headers=engineer_headers,
    )
    resp = await api_client.get("/v1/connectors?type=s3", headers=engineer_headers)
    assert resp.status_code == 200
    for c in resp.json()["data"]:
        assert c["type"] == "s3"


async def test_delete_connector_non_admin_forbidden(api_client: AsyncClient, engineer_headers: dict) -> None:
    create_resp = await api_client.post(
        "/v1/connectors",
        json={"name": "no-del-conn", "type": "postgresql"},
        headers=engineer_headers,
    )
    conn_id = create_resp.json()["data"]["id"]
    resp = await api_client.delete(f"/v1/connectors/{conn_id}", headers=engineer_headers)
    assert resp.status_code == 403
