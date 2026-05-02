"""E2E test: Airflow triggers feanor_data_validation DAG → Trino query passes.

Requires the full Docker Compose stack:
    docker compose --project-name feanor up --wait

Run with:
    pytest -m e2e tests/e2e/test_airflow_data_validation.py
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

_AIRFLOW_URL = os.environ.get("E2E_AIRFLOW_URL", "http://localhost:8090")
_AIRFLOW_USER = os.environ.get("AIRFLOW_ADMIN_USER", "admin")
_AIRFLOW_PASS = os.environ.get("AIRFLOW_ADMIN_PASSWORD", "admin")
_TRINO_URL = os.environ.get("E2E_TRINO_URL", "http://localhost:18080")

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixtures (reuse helpers from test_airflow_workflow_run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def airflow_client() -> httpx.Client:
    client = httpx.Client(
        base_url=_AIRFLOW_URL,
        auth=(_AIRFLOW_USER, _AIRFLOW_PASS),
        timeout=30.0,
    )
    try:
        client.get("/health").raise_for_status()
    except Exception as exc:
        pytest.skip(f"Airflow not reachable at {_AIRFLOW_URL}: {exc}")

    # Also check Trino is up — this DAG requires it.
    try:
        httpx.get(f"{_TRINO_URL}/v1/info", timeout=5.0).raise_for_status()
    except Exception as exc:
        pytest.skip(f"Trino not reachable at {_TRINO_URL}: {exc}")

    yield client
    client.close()


# ---------------------------------------------------------------------------
# Helpers (duplicated to keep modules self-contained)
# ---------------------------------------------------------------------------


def _set_variable(client: httpx.Client, key: str, value: str) -> None:
    resp = client.patch(f"/api/v1/variables/{key}", json={"key": key, "value": value})
    if resp.status_code == 404:
        resp = client.post("/api/v1/variables", json={"key": key, "value": value})
    resp.raise_for_status()


def _trigger_dag(client: httpx.Client, dag_id: str) -> str:
    resp = client.post(f"/api/v1/dags/{dag_id}/dagRuns", json={"conf": {}})
    resp.raise_for_status()
    return resp.json()["dag_run_id"]


def _wait_for_dag_run(
    client: httpx.Client, dag_id: str, dag_run_id: str, timeout: int = 120
) -> str:
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


def _get_task_states(client: httpx.Client, dag_id: str, dag_run_id: str) -> dict[str, str]:
    resp = client.get(
        f"/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances"
    )
    resp.raise_for_status()
    return {
        ti["task_id"]: ti["state"]
        for ti in resp.json().get("task_instances", [])
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_data_validation_passes_for_existing_table(airflow_client):
    """Trigger feanor_data_validation with a permissive assertion — should pass."""
    # Query the execution_templates table (seeded at startup) expecting ≥0 rows.
    _set_variable(
        airflow_client,
        "feanor_data_validation__sql",
        "SELECT count(*) AS cnt FROM postgresql.public.execution_templates",
    )
    _set_variable(airflow_client, "feanor_data_validation__min_rows", "0")
    _set_variable(airflow_client, "feanor_data_validation__max_rows", "")
    _set_variable(airflow_client, "feanor_data_validation__assert_expr", "")
    _unpause_dag(airflow_client, "feanor_data_validation")

    dag_run_id = _trigger_dag(airflow_client, "feanor_data_validation")
    final_state = _wait_for_dag_run(
        airflow_client, "feanor_data_validation", dag_run_id, timeout=120
    )

    task_states = _get_task_states(airflow_client, "feanor_data_validation", dag_run_id)
    print(f"Task states: {task_states}")

    assert final_state == "success", (
        f"feanor_data_validation DAG run {dag_run_id} ended with state '{final_state}'. "
        f"Task states: {task_states}"
    )
    assert task_states.get("run_query") == "success"
    assert task_states.get("assert_result") == "success"


@pytest.mark.e2e
def test_data_validation_fails_on_assertion(airflow_client):
    """Trigger feanor_data_validation with an impossible assertion — should fail."""
    _set_variable(
        airflow_client,
        "feanor_data_validation__sql",
        "SELECT count(*) AS cnt FROM postgresql.public.execution_templates",
    )
    # min_rows of 1,000,000 will definitely fail.
    _set_variable(airflow_client, "feanor_data_validation__min_rows", "1000000")
    _set_variable(airflow_client, "feanor_data_validation__max_rows", "")
    _set_variable(airflow_client, "feanor_data_validation__assert_expr", "")
    _unpause_dag(airflow_client, "feanor_data_validation")

    dag_run_id = _trigger_dag(airflow_client, "feanor_data_validation")
    final_state = _wait_for_dag_run(
        airflow_client, "feanor_data_validation", dag_run_id, timeout=120
    )

    assert final_state == "failed", (
        f"Expected DAG run to fail with impossible min_rows, got state '{final_state}'"
    )
    task_states = _get_task_states(airflow_client, "feanor_data_validation", dag_run_id)
    # run_query should succeed, assert_result should fail.
    assert task_states.get("run_query") == "success"
    assert task_states.get("assert_result") in ("failed", "upstream_failed")
