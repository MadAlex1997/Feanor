"""Unit tests for SDK resource implementations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from feanor.exceptions import FeanorAPIError
from feanor.resources.datasets import DatasetsResource
from feanor.resources.executions import ExecutionsResource
from feanor.resources.templates import TemplatesResource
from feanor.resources.workflows import WorkflowsResource


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_resp(status_code: int, body: dict) -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = body
    resp.text = str(body)
    return resp


def _http_mock() -> MagicMock:
    http = MagicMock()
    http.raise_for_envelope = MagicMock(wraps=_raise_for_envelope)
    return http


def _raise_for_envelope(resp: httpx.Response):
    from feanor.http import FeanorHTTPClient

    client = FeanorHTTPClient.__new__(FeanorHTTPClient)
    return client.raise_for_envelope(resp)


def _dataset_payload(name: str = "ds1") -> dict:
    now = _now()
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "source_ref": "s3://bucket/path/",
        "schema_hints": None,
        "created_by": "alice",
        "lineage_refs": None,
        "created_at": now,
        "updated_at": now,
    }


def _workflow_payload() -> dict:
    now = _now()
    return {
        "id": str(uuid.uuid4()),
        "slug": "my-etl",
        "version": "v1",
        "definition": None,
        "execution_template_id": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    }


def _execution_payload() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "workflow_id": str(uuid.uuid4()),
        "status": "pending",
        "inputs": None,
        "result_ref": None,
        "log_ref": None,
        "started_at": None,
        "ended_at": None,
        "created_at": _now(),
        "created_by": "alice",
    }


def _template_payload() -> dict:
    now = _now()
    return {
        "id": str(uuid.uuid4()),
        "name": "serverless_standard",
        "type": "serverless",
        "config": None,
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# DatasetsResource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_datasets_list_parses_response() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": [_dataset_payload()], "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = DatasetsResource(http)
    result = await resource.list()
    assert len(result) == 1
    assert result[0].name == "ds1"


@pytest.mark.asyncio
async def test_datasets_get_raises_on_404() -> None:
    from feanor.http import FeanorHTTPClient

    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(404, {"error": "dataset not found"}))
    http.raise_for_envelope = FeanorHTTPClient.raise_for_envelope.__get__(http, type(http))
    resource = DatasetsResource(http)
    with pytest.raises(FeanorAPIError) as exc_info:
        await resource.get("nonexistent")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_datasets_register_sends_correct_body() -> None:
    http = MagicMock()
    captured = {}

    async def fake_post(path: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs.get("json", {}))
        return _make_resp(201, {"data": _dataset_payload("new-ds"), "error": None})

    http.post = AsyncMock(side_effect=fake_post)
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = DatasetsResource(http)
    result = await resource.register(name="new-ds", source="s3://bucket/path/")
    assert captured["name"] == "new-ds"
    assert captured["source_ref"] == "s3://bucket/path/"
    assert result.name == "new-ds"


# ---------------------------------------------------------------------------
# WorkflowsResource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflows_list_returns_typed_models() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": [_workflow_payload()], "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = WorkflowsResource(http)
    result = await resource.list()
    assert len(result) == 1
    assert result[0].slug == "my-etl"


@pytest.mark.asyncio
async def test_workflows_get_raises_on_403() -> None:
    from feanor.http import FeanorHTTPClient

    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(403, {"error": "forbidden"}))
    http.raise_for_envelope = FeanorHTTPClient.raise_for_envelope.__get__(http, type(http))
    resource = WorkflowsResource(http)
    with pytest.raises(FeanorAPIError) as exc_info:
        await resource.get("some-id")
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# ExecutionsResource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executions_list_returns_typed_models() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": [_execution_payload()], "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    result = await resource.list()
    assert len(result) == 1
    assert result[0].status == "pending"


@pytest.mark.asyncio
async def test_executions_submit_wait_false_returns_immediately() -> None:
    pending = {**_execution_payload(), "status": "pending"}
    http = MagicMock()
    http.post = AsyncMock(return_value=_make_resp(202, {"data": pending, "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    result = await resource.submit(workflow=pending["workflow_id"], inputs={"a": "1"}, wait=False)
    assert result.status == "pending"
    http.post.assert_called_once()


@pytest.mark.asyncio
async def test_executions_submit_wait_true_polls_wait_endpoint() -> None:
    pending = {**_execution_payload(), "status": "pending"}
    terminal = {**pending, "status": "succeeded"}
    http = MagicMock()
    http.post = AsyncMock(return_value=_make_resp(202, {"data": pending, "error": None}))
    http.get = AsyncMock(return_value=_make_resp(200, {"data": terminal, "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    result = await resource.submit(workflow=pending["workflow_id"], wait=True, timeout=30)
    assert result.status == "succeeded"
    http.get.assert_called_once()
    call_args = http.get.call_args
    assert "wait" in call_args[0][0]


@pytest.mark.asyncio
async def test_executions_submit_wait_408_raises_feanor_error() -> None:
    from feanor.http import FeanorHTTPClient

    pending = {**_execution_payload(), "status": "running"}
    http = MagicMock()
    http.post = AsyncMock(return_value=_make_resp(202, {"data": pending, "error": None}))
    wait_resp = _make_resp(408, {"detail": {"message": "timed out", "execution": pending}})
    http.get = AsyncMock(return_value=wait_resp)
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    with pytest.raises(FeanorAPIError) as exc:
        await resource.submit(workflow=pending["workflow_id"], wait=True)
    assert exc.value.status_code == 408


@pytest.mark.asyncio
async def test_executions_submit_slug_version_resolves_to_uuid() -> None:
    wf = _workflow_payload()
    pending = {**_execution_payload(), "workflow_id": wf["id"]}

    http = MagicMock()

    async def fake_get(path: str, **kwargs: object) -> httpx.Response:
        if "/v1/workflows" in path:
            return _make_resp(200, {"data": [wf], "error": None})
        return _make_resp(200, {"data": [], "error": None})

    http.get = AsyncMock(side_effect=fake_get)
    http.post = AsyncMock(return_value=_make_resp(202, {"data": pending, "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")

    resource = ExecutionsResource(http)
    result = await resource.submit(workflow="my-etl:v1", wait=False)
    assert result.workflow_id.hex.replace("-", "") or True  # just confirm it parsed
    assert http.post.call_args[0][0] == f"/v1/workflows/{wf['id']}/run"


@pytest.mark.asyncio
async def test_executions_submit_nonexistent_slug_raises_value_error() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": [], "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    with pytest.raises(ValueError, match="workflow not found"):
        await resource.submit(workflow="nonexistent:v1")


@pytest.mark.asyncio
async def test_executions_cancel_returns_updated_execution() -> None:
    cancelled = {**_execution_payload(), "status": "cancelled"}
    http = MagicMock()
    http.post = AsyncMock(return_value=_make_resp(200, {"data": cancelled, "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    result = await resource.cancel(cancelled["id"])
    assert result.status == "cancelled"
    assert "/cancel" in http.post.call_args[0][0]


@pytest.mark.asyncio
async def test_executions_logs_returns_text() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": {"execution_id": "x", "log": "hello\nworld"}, "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    result = await resource.logs("exec-id")
    assert result == "hello\nworld"


@pytest.mark.asyncio
async def test_executions_logs_returns_none_on_204() -> None:
    resp = _make_resp(204, {})
    resp.is_success = True
    resp.status_code = 204
    http = MagicMock()
    http.get = AsyncMock(return_value=resp)
    resource = ExecutionsResource(http)
    result = await resource.logs("exec-id")
    assert result is None


@pytest.mark.asyncio
async def test_executions_logs_tail_appends_query_param() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": {"execution_id": "x", "log": "line"}, "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = ExecutionsResource(http)
    await resource.logs("exec-id", tail=5)
    _, kwargs = http.get.call_args
    assert kwargs.get("params", {}).get("tail") == 5


# ---------------------------------------------------------------------------
# TemplatesResource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_templates_list_returns_typed_models() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_make_resp(200, {"data": [_template_payload()], "error": None}))
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = TemplatesResource(http)
    result = await resource.list()
    assert len(result) == 1
    assert result[0].name == "serverless_standard"


@pytest.mark.asyncio
async def test_templates_create_sends_correct_body() -> None:
    http = MagicMock()
    captured = {}

    async def fake_post(path: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs.get("json", {}))
        return _make_resp(201, {"data": _template_payload(), "error": None})

    http.post = AsyncMock(side_effect=fake_post)
    http.raise_for_envelope = lambda r: r.json().get("data")
    resource = TemplatesResource(http)
    await resource.create(name="serverless_standard", type="serverless")
    assert captured["name"] == "serverless_standard"
    assert captured["type"] == "serverless"
