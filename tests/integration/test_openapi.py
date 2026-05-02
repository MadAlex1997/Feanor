"""Contract test: all Phase 1 endpoints appear in the OpenAPI spec."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration

_EXPECTED_PATHS = [
    "/v1/datasets",
    "/v1/datasets/{dataset_id}",
    "/v1/workflows",
    "/v1/workflows/{workflow_id}",
    "/v1/executions",
    "/v1/executions/{execution_id}",
    "/v1/templates",
    "/v1/templates/{template_id}",
    "/v1/connectors",
    "/v1/connectors/{connector_id}",
]


async def test_all_phase1_paths_in_openapi(api_client: AsyncClient) -> None:
    resp = await api_client.get("/openapi.json")
    assert resp.status_code == 200
    paths = set(resp.json()["paths"].keys())
    for expected in _EXPECTED_PATHS:
        assert expected in paths, f"Missing path in OpenAPI spec: {expected}"
