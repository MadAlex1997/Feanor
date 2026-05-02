"""Unit tests for worker SDK — ExecutionContext and WorkerClient."""
from __future__ import annotations

import base64
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------


def test_execution_context_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEANOR_API_URL", "http://api:8080")
    monkeypatch.setenv("FEANOR_CLIENT_ID", "worker-client")
    monkeypatch.setenv("FEANOR_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FEANOR_EXECUTION_ID", "exec-123")
    monkeypatch.setenv("FEANOR_INPUTS", '{"key": "value"}')

    from worker.sdk.context import ExecutionContext

    ctx = ExecutionContext()
    assert ctx.api_url == "http://api:8080"
    assert ctx.client_id == "worker-client"
    assert ctx.execution_id == "exec-123"
    assert ctx.inputs == {"key": "value"}


def test_execution_context_raises_on_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("FEANOR_API_URL", "FEANOR_CLIENT_ID", "FEANOR_CLIENT_SECRET",
                "FEANOR_EXECUTION_ID", "FEANOR_INPUTS"):
        monkeypatch.delenv(var, raising=False)

    from worker.sdk.context import ExecutionContext

    with pytest.raises(EnvironmentError, match="missing required environment variables"):
        ExecutionContext()


def test_execution_context_raises_with_partial_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEANOR_API_URL", "http://api:8080")
    for var in ("FEANOR_CLIENT_ID", "FEANOR_CLIENT_SECRET", "FEANOR_EXECUTION_ID", "FEANOR_INPUTS"):
        monkeypatch.delenv(var, raising=False)

    from worker.sdk.context import ExecutionContext

    with pytest.raises(EnvironmentError):
        ExecutionContext()


# ---------------------------------------------------------------------------
# WorkerClient
# ---------------------------------------------------------------------------


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.api_url = "http://api:8080"
    ctx.client_id = "worker"
    ctx.client_secret = "secret"
    ctx.execution_id = "exec-abc"
    ctx.inputs = {}
    return ctx


@pytest.mark.asyncio
async def test_report_running_sends_correct_payload() -> None:
    from worker.sdk.client import WorkerClient

    ctx = _make_ctx()
    wc = WorkerClient(ctx)
    wc._token = "tok"

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.raise_for_status = MagicMock()

    patched_client = AsyncMock()
    patched_client.__aenter__ = AsyncMock(return_value=patched_client)
    patched_client.__aexit__ = AsyncMock(return_value=False)
    patched_client.patch = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=patched_client):
        await wc.report_running()

    patched_client.patch.assert_called_once()
    _, kwargs = patched_client.patch.call_args
    assert kwargs["json"]["status"] == "running"
    assert "exec-abc" in patched_client.patch.call_args[0][0]


@pytest.mark.asyncio
async def test_report_succeeded_sends_correct_payload() -> None:
    from worker.sdk.client import WorkerClient

    ctx = _make_ctx()
    wc = WorkerClient(ctx)
    wc._token = "tok"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    patched_client = AsyncMock()
    patched_client.__aenter__ = AsyncMock(return_value=patched_client)
    patched_client.__aexit__ = AsyncMock(return_value=False)
    patched_client.patch = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=patched_client):
        await wc.report_succeeded("s3://bucket/key")

    _, kwargs = patched_client.patch.call_args
    assert kwargs["json"]["status"] == "succeeded"
    assert kwargs["json"]["result_ref"] == "s3://bucket/key"


@pytest.mark.asyncio
async def test_report_failed_encodes_message() -> None:
    from worker.sdk.client import WorkerClient

    ctx = _make_ctx()
    wc = WorkerClient(ctx)
    wc._token = "tok"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    patched_client = AsyncMock()
    patched_client.__aenter__ = AsyncMock(return_value=patched_client)
    patched_client.__aexit__ = AsyncMock(return_value=False)
    patched_client.patch = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=patched_client):
        await wc.report_failed("something went wrong")

    _, kwargs = patched_client.patch.call_args
    log_ref = kwargs["json"]["log_ref"]
    assert log_ref.startswith("inline:")
    decoded = base64.b64decode(log_ref[len("inline:"):]).decode()
    assert "something went wrong" in decoded
