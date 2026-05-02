"""Fixtures for end-to-end tests (Phase 3 + Phase 4).

All tests in this directory require the full Docker Compose stack:
    docker compose --project-name feanor up --wait

Run with:
    pytest -m e2e

Skip in CI unit/integration runs:
    pytest -m "not e2e"
"""
from __future__ import annotations

import os
import pathlib
import uuid

import pytest
import pytest_asyncio

_API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")
_TRINO_URL = os.environ.get("E2E_TRINO_URL", "http://localhost:18080")
_MINIO_URL = os.environ.get("E2E_MINIO_URL", "http://localhost:9000")
_MINIO_ACCESS = os.environ.get("MINIO_ROOT_USER", "minioadmin")
_MINIO_SECRET = os.environ.get("MINIO_ROOT_PASSWORD", "changeme")

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"
_SAMPLE_PARQUET = _FIXTURE_DIR / "sample_data.parquet"

_TEST_BUCKET = "feanor-test"
_SAMPLE_KEY = "test-data/sample.parquet"


def _check_stack() -> None:
    """Skip the test if the Docker Compose stack is not reachable."""
    import httpx

    try:
        resp = httpx.get(f"{_API_URL}/health", timeout=3.0)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Docker Compose stack not reachable at {_API_URL}: {exc}")

    try:
        resp = httpx.get(f"{_TRINO_URL}/v1/info", timeout=3.0)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Trino not reachable at {_TRINO_URL}: {exc}")


@pytest.fixture(scope="session", autouse=True)
def stack_check() -> None:
    """Session-scoped guard: skip all e2e tests if the stack is down."""
    _check_stack()


@pytest.fixture(scope="session")
def minio_client():
    """Boto3 S3 client pointed at the local MinIO instance."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=_MINIO_URL,
        aws_access_key_id=_MINIO_ACCESS,
        aws_secret_access_key=_MINIO_SECRET,
        region_name="us-east-1",
    )


@pytest.fixture(scope="session")
def setup_test_bucket(minio_client):
    """Create the test bucket and upload the sample Parquet; tear down after session."""
    try:
        minio_client.create_bucket(Bucket=_TEST_BUCKET)
    except minio_client.exceptions.BucketAlreadyOwnedByYou:
        pass
    except Exception:
        pass  # Bucket likely already exists.

    minio_client.upload_file(
        str(_SAMPLE_PARQUET),
        _TEST_BUCKET,
        _SAMPLE_KEY,
    )

    yield

    # Cleanup: delete the uploaded object.
    try:
        minio_client.delete_object(Bucket=_TEST_BUCKET, Key=_SAMPLE_KEY)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="session")
async def e2e_client():
    """Authenticated feanor AsyncClient pointed at the local stack.

    Uses a pre-set token header via FEANOR_TOKEN env var or a dev bypass.
    """
    import httpx

    from feanor.async_client import AsyncClient
    from feanor.config import Profile

    # For local e2e tests, use a direct API client with the engineer bypass headers
    # (the same pattern as integration tests: X-Feanor-Roles header).
    # In a real environment this would use device flow / client credentials.
    profile = Profile(
        name="e2e",
        api_url=_API_URL,
        keycloak_url="http://localhost:8080",
        realm="feanor",
        trino_url=_TRINO_URL,
    )

    async with AsyncClient.__new__(AsyncClient) as client:
        # Bypass full auth for local e2e by injecting headers at the httpx level.
        from feanor.http import FeanorHTTPClient

        http = FeanorHTTPClient.__new__(FeanorHTTPClient)
        http._profile = profile
        http._client = httpx.AsyncClient(
            base_url=_API_URL,
            timeout=30.0,
            headers={
                "X-Feanor-Subject": "e2e-engineer",
                "X-Feanor-Roles": "engineer",
                "Authorization": "Bearer e2e-bypass",
            },
        )

        class _NoOpTokenManager:
            def get_token(self):
                return "e2e-bypass"

        http._token_manager = _NoOpTokenManager()

        from feanor.resources.datasets import DatasetsResource
        from feanor.resources.executions import ExecutionsResource
        from feanor.resources.query import QueryResource
        from feanor.resources.system import SystemResource
        from feanor.resources.templates import TemplatesResource
        from feanor.resources.workflows import WorkflowsResource

        client._resolved = profile
        client._http = http
        client.datasets = DatasetsResource(http)
        client.workflows = WorkflowsResource(http)
        client.executions = ExecutionsResource(http)
        client.templates = TemplatesResource(http)
        client.system = SystemResource(http)
        client._query_resource = QueryResource(profile)

        yield client

        await http._client.aclose()


# ---------------------------------------------------------------------------
# Phase 4 — Airflow helpers
# ---------------------------------------------------------------------------

_AIRFLOW_URL = os.environ.get("E2E_AIRFLOW_URL", "http://localhost:8090")
_AIRFLOW_USER = os.environ.get("AIRFLOW_ADMIN_USER", "admin")
_AIRFLOW_PASS = os.environ.get("AIRFLOW_ADMIN_PASSWORD", "admin")


@pytest.fixture(scope="session")
def airflow_api_client():
    """Synchronous httpx client for the Airflow REST API.

    Skips if Airflow is not reachable (Phase 3 tests that don't need it).
    """
    import httpx

    client = httpx.Client(
        base_url=_AIRFLOW_URL,
        auth=(_AIRFLOW_USER, _AIRFLOW_PASS),
        timeout=30.0,
    )
    try:
        client.get("/health").raise_for_status()
    except Exception as exc:
        pytest.skip(f"Airflow not reachable at {_AIRFLOW_URL}: {exc}")

    yield client
    client.close()


def set_airflow_variable(client, key: str, value: str) -> None:
    """Upsert an Airflow Variable via the REST API."""
    import httpx

    resp = client.patch(f"/api/v1/variables/{key}", json={"key": key, "value": value})
    if resp.status_code == 404:
        resp = client.post("/api/v1/variables", json={"key": key, "value": value})
    resp.raise_for_status()


def trigger_dag_run(client, dag_id: str) -> str:
    """Trigger a DAG run and return the dag_run_id."""
    import time

    # Unpause the DAG first (new DAGs start paused).
    client.patch(f"/api/v1/dags/{dag_id}", json={"is_paused": False})
    time.sleep(1)

    resp = client.post(f"/api/v1/dags/{dag_id}/dagRuns", json={"conf": {}})
    resp.raise_for_status()
    return resp.json()["dag_run_id"]


def wait_for_dag_run(client, dag_id: str, dag_run_id: str, timeout: int = 120) -> str:
    """Poll until the DAG run is in a terminal state. Returns the final state."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}")
        resp.raise_for_status()
        state = resp.json()["state"]
        if state in ("success", "failed"):
            return state
        time.sleep(5)
    raise TimeoutError(
        f"DAG run {dag_run_id} for '{dag_id}' did not reach terminal state "
        f"within {timeout}s"
    )
