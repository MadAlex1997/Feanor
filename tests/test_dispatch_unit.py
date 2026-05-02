"""Unit tests for the Docker dispatcher — mocked Docker SDK."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.app.models.execution import Execution, ExecutionStatus


def _make_execution(**kw) -> MagicMock:
    e = MagicMock(spec=Execution)
    e.id = kw.get("id", uuid.uuid4())
    e.workflow_id = kw.get("workflow_id", uuid.uuid4())
    e.status = kw.get("status", ExecutionStatus.pending)
    e.inputs = kw.get("inputs", {})
    e.result_ref = kw.get("result_ref", None)
    e.log_ref = kw.get("log_ref", None)
    e.cancel_requested = kw.get("cancel_requested", False)
    e.started_at = kw.get("started_at", None)
    e.ended_at = kw.get("ended_at", None)
    e.created_at = kw.get("created_at", datetime.now(timezone.utc))
    e.created_by = kw.get("created_by", "alice")
    return e


def _make_template(name="serverless_standard", ttype="serverless", config=None) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.type = MagicMock()
    t.type.value = ttype
    t.config = config or {}
    return t


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# run_container — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_container_success_sets_succeeded() -> None:
    from api.app.dispatch.docker_runner import run_container

    execution = _make_execution()
    template = _make_template()
    db = _make_db()

    fake_container = MagicMock()
    fake_container.status = "exited"
    fake_container.attrs = {"State": {"ExitCode": 0}}
    fake_container.logs.return_value = b"success output"

    def _fake_reload():
        pass

    fake_container.reload = _fake_reload

    fake_docker_client = MagicMock()
    fake_docker_client.containers.run.return_value = fake_container

    with patch("docker.from_env", return_value=fake_docker_client):
        with patch("asyncio.to_thread", new=AsyncMock(return_value=(0, "success output"))):
            await run_container(execution, template, db)

    assert execution.status == ExecutionStatus.succeeded


@pytest.mark.asyncio
async def test_run_container_nonzero_exit_sets_failed() -> None:
    from api.app.dispatch.docker_runner import run_container

    execution = _make_execution()
    template = _make_template()
    db = _make_db()

    with patch("asyncio.to_thread", new=AsyncMock(return_value=(1, "error output"))):
        await run_container(execution, template, db)

    assert execution.status == ExecutionStatus.failed
    assert execution.log_ref is not None
    decoded = base64.b64decode(execution.log_ref.split(":", 1)[1]).decode()
    assert "error output" in decoded


@pytest.mark.asyncio
async def test_run_container_timeout_sets_failed() -> None:
    from api.app.dispatch.docker_runner import run_container

    execution = _make_execution()
    template = _make_template()
    db = _make_db()

    with patch("asyncio.to_thread", new=AsyncMock(return_value=(-1, "timeout"))):
        await run_container(execution, template, db)

    assert execution.status == ExecutionStatus.failed


@pytest.mark.asyncio
async def test_run_container_image_not_found_sets_failed() -> None:
    from api.app.dispatch.docker_runner import run_container

    execution = _make_execution()
    template = _make_template()
    db = _make_db()

    import docker.errors

    with patch("asyncio.to_thread", new=AsyncMock(side_effect=docker.errors.ImageNotFound("img"))):
        await run_container(execution, template, db)

    assert execution.status == ExecutionStatus.failed
    assert "image not found" in base64.b64decode(execution.log_ref.split(":", 1)[1]).decode()


@pytest.mark.asyncio
async def test_run_container_distributed_not_supported() -> None:
    from api.app.dispatch.docker_runner import run_container

    execution = _make_execution()
    template = _make_template(name="distributed_spark_medium", ttype="distributed")
    db = _make_db()

    await run_container(execution, template, db)

    assert execution.status == ExecutionStatus.failed
    decoded = base64.b64decode(execution.log_ref.split(":", 1)[1]).decode()
    assert "distributed" in decoded


# ---------------------------------------------------------------------------
# is_valid_transition
# ---------------------------------------------------------------------------


def test_valid_transitions() -> None:
    from api.app.dispatch import is_valid_transition

    assert is_valid_transition(ExecutionStatus.pending, ExecutionStatus.running)
    assert is_valid_transition(ExecutionStatus.pending, ExecutionStatus.cancelled)
    assert is_valid_transition(ExecutionStatus.running, ExecutionStatus.succeeded)
    assert is_valid_transition(ExecutionStatus.running, ExecutionStatus.failed)
    assert is_valid_transition(ExecutionStatus.running, ExecutionStatus.cancelled)


def test_invalid_transitions() -> None:
    from api.app.dispatch import is_valid_transition

    assert not is_valid_transition(ExecutionStatus.pending, ExecutionStatus.succeeded)
    assert not is_valid_transition(ExecutionStatus.pending, ExecutionStatus.failed)
    assert not is_valid_transition(ExecutionStatus.succeeded, ExecutionStatus.running)
    assert not is_valid_transition(ExecutionStatus.failed, ExecutionStatus.running)
    assert not is_valid_transition(ExecutionStatus.cancelled, ExecutionStatus.running)
