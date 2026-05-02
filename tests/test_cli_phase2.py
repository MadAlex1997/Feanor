"""Unit tests for Phase 2 CLI commands — workflows run, executions cancel/logs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from feanor.cli import app
from feanor.exceptions import FeanorAPIError
from feanor.models.execution import Execution

runner = CliRunner()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_execution(**kw) -> Execution:
    return Execution(
        id=kw.get("id", uuid.uuid4()),
        workflow_id=kw.get("workflow_id", uuid.uuid4()),
        status=kw.get("status", "pending"),
        inputs=kw.get("inputs", None),
        result_ref=kw.get("result_ref", None),
        log_ref=kw.get("log_ref", None),
        created_at=kw.get("created_at", _now()),
        created_by=kw.get("created_by", "alice"),
    )


_UNSET = object()


def _make_async_client(submit_result=_UNSET, cancel_result=_UNSET, logs_result=_UNSET, get_result=_UNSET):
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    client.executions = AsyncMock()
    if submit_result is not _UNSET:
        client.executions.submit = AsyncMock(return_value=submit_result)
    if cancel_result is not _UNSET:
        client.executions.cancel = AsyncMock(return_value=cancel_result)
    if logs_result is not _UNSET:
        client.executions.logs = AsyncMock(return_value=logs_result)
    if get_result is not _UNSET:
        client.executions.get = AsyncMock(return_value=get_result)

    return client


# ---------------------------------------------------------------------------
# feanor workflows run
# ---------------------------------------------------------------------------


def test_workflows_run_calls_submit_with_correct_args() -> None:
    exc = _make_execution(status="pending")
    client = _make_async_client(submit_result=exc)

    with patch("feanor.cli.commands.workflows.AsyncClient", return_value=client):
        result = runner.invoke(
            app,
            ["workflows", "run", "slug:version", "--input", "a=1", "--input", "b=2"],
        )

    assert result.exit_code == 0
    client.executions.submit.assert_called_once_with(
        workflow="slug:version",
        inputs={"a": "1", "b": "2"},
        wait=False,
        timeout=60,
    )


def test_workflows_run_wait_passes_wait_true() -> None:
    exc = _make_execution(status="succeeded")
    client = _make_async_client(submit_result=exc)

    with patch("feanor.cli.commands.workflows.AsyncClient", return_value=client):
        result = runner.invoke(
            app,
            ["workflows", "run", "slug:version", "--wait", "--timeout", "30"],
        )

    assert result.exit_code == 0
    client.executions.submit.assert_called_once_with(
        workflow="slug:version",
        inputs=None,
        wait=True,
        timeout=30,
    )


def test_workflows_run_408_exits_with_code_1() -> None:
    client = _make_async_client()
    client.executions.submit = AsyncMock(
        side_effect=FeanorAPIError(408, "execution timed out waiting for terminal status")
    )

    with patch("feanor.cli.commands.workflows.AsyncClient", return_value=client):
        result = runner.invoke(app, ["workflows", "run", "slug:version", "--wait"])

    assert result.exit_code == 1
    assert "timed out" in result.output.lower() or "timed out" in (result.stderr or "").lower()


def test_workflows_run_bad_input_raises_error() -> None:
    result = runner.invoke(app, ["workflows", "run", "slug:version", "--input", "badformat"])
    assert result.exit_code != 0


def test_workflows_run_input_with_equals_in_value() -> None:
    exc = _make_execution()
    client = _make_async_client(submit_result=exc)

    with patch("feanor.cli.commands.workflows.AsyncClient", return_value=client):
        result = runner.invoke(
            app,
            ["workflows", "run", "slug:version", "--input", "url=https://example.com?a=1"],
        )

    assert result.exit_code == 0
    _, kwargs = client.executions.submit.call_args
    assert kwargs["inputs"]["url"] == "https://example.com?a=1"


# ---------------------------------------------------------------------------
# feanor executions cancel
# ---------------------------------------------------------------------------


def test_executions_cancel_calls_cancel_and_prints() -> None:
    exc_id = str(uuid.uuid4())
    cancelled = _make_execution(id=uuid.UUID(exc_id), status="cancelled")
    client = _make_async_client(cancel_result=cancelled)

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "cancel", exc_id])

    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()
    client.executions.cancel.assert_called_once_with(exc_id)


def test_executions_cancel_409_exits_code_1() -> None:
    exc_id = str(uuid.uuid4())
    client = _make_async_client()
    client.executions.cancel = AsyncMock(
        side_effect=FeanorAPIError(409, "execution already in terminal state")
    )

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "cancel", exc_id])

    assert result.exit_code == 1


def test_executions_cancel_404_exits_code_2() -> None:
    exc_id = str(uuid.uuid4())
    client = _make_async_client()
    client.executions.cancel = AsyncMock(side_effect=FeanorAPIError(404, "not found"))

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "cancel", exc_id])

    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# feanor executions logs
# ---------------------------------------------------------------------------


def test_executions_logs_prints_log_text() -> None:
    exc_id = str(uuid.uuid4())
    client = _make_async_client(logs_result="line1\nline2")

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "logs", exc_id])

    assert result.exit_code == 0
    assert "line1" in result.output


def test_executions_logs_204_prints_no_logs_message() -> None:
    exc_id = str(uuid.uuid4())
    client = _make_async_client(logs_result=None)

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "logs", exc_id])

    assert result.exit_code == 0
    assert "no logs available" in result.output.lower() or "no logs available" in (result.stderr or "").lower()


def test_executions_logs_tail_passes_tail_to_sdk() -> None:
    exc_id = str(uuid.uuid4())
    client = _make_async_client(logs_result="only line")

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "logs", exc_id, "--tail", "10"])

    assert result.exit_code == 0
    client.executions.logs.assert_called_once_with(exc_id, tail=10)


def test_executions_logs_follow_polls_until_terminal() -> None:
    exc_id = str(uuid.uuid4())
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.executions = AsyncMock()

    call_count = 0

    async def fake_logs(eid, tail=None, follow=False):
        nonlocal call_count
        call_count += 1
        return f"line{call_count}"

    succeeded_exec = _make_execution(status="succeeded")

    client.executions.logs = fake_logs
    client.executions.get = AsyncMock(return_value=succeeded_exec)

    with patch("feanor.cli.commands.executions.AsyncClient", return_value=client):
        result = runner.invoke(app, ["executions", "logs", exc_id, "--follow"])

    # Should have exited cleanly once terminal status was reached
    assert result.exit_code == 0
