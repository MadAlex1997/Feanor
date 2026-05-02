"""E2E test: Airflow triggers feanor_workflow_run DAG → control plane execution.

Requires the full Docker Compose stack:
    docker compose --project-name feanor up --wait

Run with:
    pytest -m e2e tests/e2e/test_airflow_workflow_run.py
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

_AIRFLOW_URL = os.environ.get("E2E_AIRFLOW_URL", "http://localhost:8090")
_API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")
_AIRFLOW_USER = os.environ.get("AIRFLOW_ADMIN_USER", "admin")
_AIRFLOW_PASS = os.environ.get("AIRFLOW_ADMIN_PASSWORD", "admin")

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def airflow_client() -> httpx.Client:
    """Synchronous httpx client authenticated against the Airflow REST API."""
    client = httpx.Client(
        base_url=_AIRFLOW_URL,
        auth=(_AIRFLOW_USER, _AIRFLOW_PASS),
        timeout=30.0,
    )
    # Check Airflow is reachable.
    try:
        resp = client.get("/health")
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Airflow not reachable at {_AIRFLOW_URL}: {exc}")
    yield client
    client.close()


@pytest.fixture(scope="module")
def control_plane_client() -> httpx.Client:
    client = httpx.Client(
        base_url=_API_URL,
        headers={"X-Feanor-Subject": "e2e-engineer", "X-Feanor-Roles": "engineer"},
        timeout=30.0,
    )
    try:
        client.get("/health").raise_for_status()
    except Exception as exc:
        pytest.skip(f"Control plane not reachable at {_API_URL}: {exc}")
    yield client
    client.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_variable(client: httpx.Client, key: str, value: str) -> None:
    resp = client.patch(
        f"/api/v1/variables/{key}",
        json={"key": key, "value": value},
    )
    if resp.status_code == 404:
        resp = client.post("/api/v1/variables", json={"key": key, "value": value})
    resp.raise_for_status()


def _trigger_dag(client: httpx.Client, dag_id: str) -> str:
    resp = client.post(
        f"/api/v1/dags/{dag_id}/dagRuns",
        json={"conf": {}},
    )
    resp.raise_for_status()
    return resp.json()["dag_run_id"]


def _wait_for_dag_run(
    client: httpx.Client,
    dag_id: str,
    dag_run_id: str,
    timeout: int = 120,
) -> str:
    """Poll until the DAG run reaches a terminal state. Returns the final state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}")
        resp.raise_for_status()
        state = resp.json()["state"]
        if state in ("success", "failed"):
            return state
        time.sleep(5)
    raise TimeoutError(
        f"DAG run {dag_run_id} did not reach terminal state within {timeout}s"
    )


def _unpause_dag(client: httpx.Client, dag_id: str) -> None:
    client.patch(f"/api/v1/dags/{dag_id}", json={"is_paused": False})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_workflow_run_dag_creates_execution(airflow_client, control_plane_client):
    """Trigger feanor_workflow_run and assert an execution record is created."""
    # Point at a workflow slug that the no-op dispatcher can handle.
    # The example-workflow:v1 slug is seeded by the init scripts.
    _set_variable(airflow_client, "feanor_workflow_run__workflow_slug", "example-workflow:v1")
    _set_variable(airflow_client, "feanor_workflow_run__inputs", "{}")
    _unpause_dag(airflow_client, "feanor_workflow_run")

    # Count executions before trigger.
    before_resp = control_plane_client.get(
        "/v1/executions", params={"limit": 100}
    )
    before_count = len(before_resp.json().get("data", []))

    dag_run_id = _trigger_dag(airflow_client, "feanor_workflow_run")
    final_state = _wait_for_dag_run(
        airflow_client, "feanor_workflow_run", dag_run_id, timeout=180
    )

    # Diagnose failures by printing task instance logs.
    if final_state != "success":
        ti_resp = airflow_client.get(
            f"/api/v1/dags/feanor_workflow_run/dagRuns/{dag_run_id}/taskInstances"
        )
        for ti in ti_resp.json().get("task_instances", []):
            print(
                f"Task {ti['task_id']}: {ti['state']} "
                f"(try={ti.get('try_number', '?')})"
            )

    assert final_state == "success", (
        f"feanor_workflow_run DAG run {dag_run_id} ended with state '{final_state}'"
    )

    # Verify the execution record was created in the control plane.
    after_resp = control_plane_client.get(
        "/v1/executions", params={"limit": 100}
    )
    after_data = after_resp.json().get("data", [])
    assert len(after_data) > before_count, (
        "Expected at least one new execution record after DAG run, but count did not increase."
    )

    # The most recent execution should be succeeded.
    latest = sorted(after_data, key=lambda e: e.get("created_at", ""), reverse=True)[0]
    assert latest["status"] in ("succeeded", "running"), (
        f"Unexpected execution status: {latest['status']}"
    )
