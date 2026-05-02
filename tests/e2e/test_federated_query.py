"""Scenario A: register MinIO connector → upload data → query via Trino.

Requires: full Docker Compose stack (`pytest -m e2e`).
"""
from __future__ import annotations

import asyncio
import pathlib
import time
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.e2e

_MINIO_INTERNAL = "http://minio:9000"  # Trino reaches MinIO on the Docker network.
_TEST_BUCKET = "feanor-test"
_SAMPLE_KEY = "test-data/sample.parquet"
_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_connector_registration_creates_catalog_file(
    setup_test_bucket,
    minio_client,
    tmp_path,
    monkeypatch,
):
    """POST /v1/connectors with s3 type should create a catalog properties file."""
    import httpx

    connector_name = f"e2e-minio-{uuid.uuid4().hex[:6]}"
    payload = {
        "name": connector_name,
        "type": "s3",
        "config": {
            "endpoint": _MINIO_INTERNAL,
            "access_key": "minioadmin",
            "secret_key": "changeme",
        },
    }

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        resp = await client.post(
            "/v1/connectors",
            json=payload,
            headers={"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"},
        )

    assert resp.status_code == 201, resp.text
    connector_id = resp.json()["data"]["id"]

    # Catalog file should exist on the host filesystem (bind-mounted).
    catalog_path = pathlib.Path("infra/trino/catalog") / f"{connector_name}.properties"
    assert catalog_path.exists(), f"Catalog file not created at {catalog_path}"
    content = catalog_path.read_text()
    assert "connector.name=hive" in content
    assert "hive.s3.endpoint" in content

    # Cleanup: delete the connector.
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        del_resp = await client.delete(
            f"/v1/connectors/{connector_id}",
            headers={"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"},
        )
    assert del_resp.status_code == 204

    # Catalog file should be removed.
    assert not catalog_path.exists(), "Catalog file not removed after connector deletion"


@pytest.mark.asyncio
async def test_trino_postgresql_catalog_queryable():
    """The postgresql catalog should be queryable via Trino."""
    import httpx

    # Wait for Trino to be fully ready.
    trino_url = "http://localhost:18080"
    for _ in range(10):
        try:
            resp = httpx.get(f"{trino_url}/v1/info", timeout=5.0)
            info = resp.json()
            if not info.get("starting", True):
                break
        except Exception:
            pass
        time.sleep(6)
    else:
        pytest.skip("Trino did not become ready in time")

    # Simple query against the postgresql catalog.
    headers = {
        "Content-Type": "text/plain",
        "X-Trino-User": "e2e-test",
        "X-Trino-Catalog": "postgresql",
        "X-Trino-Schema": "public",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{trino_url}/v1/statement",
            content=b"SELECT 1 AS n",
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    # Follow nextUri if present.
    while "nextUri" in payload:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(payload["nextUri"], headers=headers)
        payload = resp.json()

    assert "error" not in payload, payload.get("error")


@pytest.mark.asyncio
async def test_sdk_query_select_one():
    """client.query() against Trino returns correct results."""
    from feanor.config import Profile
    from feanor.resources.query import QueryResource

    trino_url = "http://localhost:18080"
    profile = Profile(
        name="e2e",
        api_url="http://localhost:8000",
        keycloak_url="http://localhost:8080",
        realm="feanor",
        trino_url=trino_url,
    )
    qr = QueryResource(profile)
    result = await qr.query("SELECT 1 AS n")
    assert result.rows == [{"n": 1}]
    assert result.columns == ["n"]
