"""Execution dispatcher — routes executions to the appropriate backend."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.app.models.execution import Execution, ExecutionStatus


# Valid status transitions enforced in code.
VALID_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.pending: {ExecutionStatus.running, ExecutionStatus.cancelled},
    ExecutionStatus.running: {
        ExecutionStatus.succeeded,
        ExecutionStatus.failed,
        ExecutionStatus.cancelled,
    },
}


def is_valid_transition(current: ExecutionStatus, target: ExecutionStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())


async def update_execution_status(
    execution: Execution,
    status: ExecutionStatus,
    db: AsyncSession,
    *,
    result_ref: str | None = None,
    log_ref: str | None = None,
) -> None:
    """Apply a status transition directly to the DB object."""
    execution.status = status
    if status == ExecutionStatus.running and execution.started_at is None:
        execution.started_at = datetime.now(timezone.utc)
    if status in (ExecutionStatus.succeeded, ExecutionStatus.failed, ExecutionStatus.cancelled):
        execution.ended_at = datetime.now(timezone.utc)
    if result_ref is not None:
        execution.result_ref = result_ref
    if log_ref is not None:
        execution.log_ref = log_ref
    await db.flush()


async def dispatch_execution(execution_id: uuid.UUID, db: AsyncSession) -> None:
    """Dispatch an execution to the appropriate runner.

    Loads the execution + workflow + template, sets status = running,
    then hands off to the Docker runner. Falls back to the stub on import
    errors (e.g. Docker SDK not installed).
    """
    from sqlalchemy import select

    stmt = (
        select(Execution)
        .where(Execution.id == execution_id)
        .options(selectinload(Execution.workflow))
    )
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()
    if execution is None:
        return

    try:
        from api.app.dispatch.docker_runner import run_container
        from api.app.models.template import ExecutionTemplate

        template = await db.get(ExecutionTemplate, execution.workflow.execution_template_id)
        if template is None:
            await update_execution_status(
                execution,
                ExecutionStatus.failed,
                db,
                log_ref="inline:" + __import__("base64").b64encode(
                    b"execution template not found"
                ).decode(),
            )
            await db.commit()
            return

        await update_execution_status(execution, ExecutionStatus.running, db)
        await db.commit()
        await run_container(execution, template, db)

    except Exception as exc:
        import base64
        log_msg = f"dispatcher error: {exc}"
        try:
            execution.status = ExecutionStatus.failed
            execution.ended_at = datetime.now(timezone.utc)
            execution.log_ref = "inline:" + base64.b64encode(log_msg.encode()).decode()
            await db.flush()
            await db.commit()
        except Exception:
            pass
