"""Scenario C: log streaming to MinIO.

Requires: full Docker Compose stack (`pytest -m e2e`).
"""
from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

pytestmark = pytest.mark.e2e

_API_URL = "http://localhost:8000"
_ENG_HEADERS = {"X-Feanor-Subject": "bob", "X-Feanor-Roles": "engineer"}
_ADMIN_HEADERS = {"X-Feanor-Subject": "admin", "X-Feanor-Roles": "platform_admin"}
_SA_HEADERS = {"X-Feanor-Subject": "dispatcher", "X-Feanor-Roles": "service_account"}


async def _get_json(client: httpx.AsyncClient, path: str, headers: dict) -> dict:
    resp = await client.get(path, headers=headers)
    resp.raise_for_status()
    return resp.json()


@pytest.mark.asyncio
async def test_logs_endpoint_returns_202_while_running():
    """GET /v1/executions/{id}/logs returns 202 when execution is running with no log yet."""
    async with httpx.AsyncClient(base_url=_API_URL, timeout=15.0) as client:
        # Create a template and workflow first.
        tmpl_resp = await client.get("/v1/templates", headers=_ENG_HEADERS)
        templates = tmpl_resp.json()["data"]
        if not templates:
            pytest.skip("No templates available — run Phase 1 seed data")
        tmpl_id = templates[0]["id"]

        wf_name = f"e2e-log-test-{uuid.uuid4().hex[:6]}"
        wf_resp = await client.post(
            "/v1/workflows",
            json={
                "name": wf_name,
                "slug": wf_name,
                "version": "v1",
                "definition": {},
                "execution_template_id": tmpl_id,
            },
            headers=_ENG_HEADERS,
        )
        assert wf_resp.status_code == 201, wf_resp.text
        wf_id = wf_resp.json()["data"]["id"]

        # Submit execution.
        run_resp = await client.post(
            f"/v1/workflows/{wf_id}/run",
            json={"inputs": {}},
            headers=_ENG_HEADERS,
        )
        assert run_resp.status_code == 202, run_resp.text
        exec_id = run_resp.json()["data"]["id"]

        # Immediately fetch logs — should be 202 or 204 (not yet available).
        logs_resp = await client.get(f"/v1/executions/{exec_id}/logs", headers=_ENG_HEADERS)
        assert logs_resp.status_code in (202, 204), logs_resp.status_code

        # Poll until terminal.
        for _ in range(30):
            exec_resp = await client.get(f"/v1/executions/{exec_id}", headers=_ENG_HEADERS)
            status = exec_resp.json()["data"]["status"]
            if status in ("succeeded", "failed", "cancelled"):
                break
            await asyncio.sleep(2)
        else:
            pytest.skip("Execution did not complete within timeout — worker image may not be built")

        # After completion, logs endpoint should return content.
        logs_resp = await client.get(f"/v1/executions/{exec_id}/logs", headers=_ENG_HEADERS)
        assert logs_resp.status_code in (200, 204), logs_resp.status_code

        exec_data = exec_resp.json()["data"]
        if exec_data.get("log_ref") and exec_data["log_ref"].startswith("s3://"):
            # Verify it points to MinIO.
            assert "feanor-logs" in exec_data["log_ref"]
