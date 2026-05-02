"""Executions API — read, submit, status, logs, cancel, wait."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db import AsyncSessionLocal, get_db
from api.app.deps import ANALYST, ENGINEER, PLATFORM_ADMIN, SERVICE_ACCOUNT, CurrentUser, require_roles
from api.app.dispatch import VALID_TRANSITIONS, dispatch_execution, is_valid_transition, update_execution_status
from api.app.dispatch.logs import fetch_log
from api.app.storage import stream_log
from api.app.models.execution import Execution, ExecutionStatus
from api.app.schemas import APIResponse, Meta
from api.app.schemas.execution import ExecutionRead, ExecutionStatusUpdate
from api.app.schemas.pagination import PaginatedMeta, decode_cursor, encode_cursor

router = APIRouter(prefix="/executions", tags=["executions"])

_ANY_ROLE = require_roles(ANALYST, ENGINEER, PLATFORM_ADMIN, SERVICE_ACCOUNT)
_PRIVILEGED = require_roles(ANALYST, ENGINEER, PLATFORM_ADMIN, SERVICE_ACCOUNT)
_SERVICE_ONLY = require_roles(SERVICE_ACCOUNT)

_TERMINAL = {ExecutionStatus.succeeded, ExecutionStatus.failed, ExecutionStatus.cancelled}


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


def _is_privileged(user: CurrentUser) -> bool:
    return ENGINEER in user.roles or PLATFORM_ADMIN in user.roles or SERVICE_ACCOUNT in user.roles


def _check_visibility(execution: Execution, user: CurrentUser) -> None:
    if not _is_privileged(user) and execution.created_by != user.subject:
        raise HTTPException(status_code=403, detail="not your execution")


@router.get("")
async def list_executions(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    workflow_id: uuid.UUID | None = Query(None),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    stmt = select(Execution)

    if not _is_privileged(current_user):
        stmt = stmt.where(Execution.created_by == current_user.subject)

    if status:
        status_values = [s.strip() for s in status.split(",") if s.strip()]
        valid = {e.value for e in ExecutionStatus}
        bad = [s for s in status_values if s not in valid]
        if bad:
            raise HTTPException(status_code=400, detail=f"invalid status values: {bad}")
        stmt = stmt.where(Execution.status.in_(status_values))

    if workflow_id:
        stmt = stmt.where(Execution.workflow_id == workflow_id)

    if cursor:
        try:
            cur_ts, cur_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid cursor")
        if order.lower() == "desc":
            stmt = stmt.where(
                or_(
                    Execution.created_at < cur_ts,
                    (Execution.created_at == cur_ts) & (Execution.id < cur_id),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    Execution.created_at > cur_ts,
                    (Execution.created_at == cur_ts) & (Execution.id > cur_id),
                )
            )

    if order.lower() == "desc":
        stmt = stmt.order_by(Execution.created_at.desc(), Execution.id.desc())
    else:
        stmt = stmt.order_by(Execution.created_at.asc(), Execution.id.asc())

    stmt = stmt.limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    total_q = select(func.count()).select_from(Execution)
    if not _is_privileged(current_user):
        total_q = total_q.where(Execution.created_by == current_user.subject)
    total = (await db.execute(total_q)).scalar_one()

    return APIResponse(
        data=[ExecutionRead.model_validate(r) for r in rows],
        meta=PaginatedMeta(
            request_id=request.state.request_id,
            cursor=next_cursor,
            limit=limit,
            total=total,
        ),
    )


@router.get("/{execution_id}")
async def get_execution(
    execution_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(Execution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")
    _check_visibility(row, current_user)
    return APIResponse(data=ExecutionRead.model_validate(row), meta=_meta(request))


@router.patch("/{execution_id}/status")
async def update_execution_status_endpoint(
    execution_id: uuid.UUID,
    body: ExecutionStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _SERVICE_ONLY,
) -> Any:
    row = await db.get(Execution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")

    try:
        target = ExecutionStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid status: {body.status}")

    if not is_valid_transition(row.status, target):
        raise HTTPException(
            status_code=409,
            detail=f"invalid transition: {row.status.value} → {target.value}",
        )

    await update_execution_status(
        row, target, db, result_ref=body.result_ref, log_ref=body.log_ref
    )
    return APIResponse(data=ExecutionRead.model_validate(row), meta=_meta(request))


@router.get("/{execution_id}/logs")
async def get_execution_logs(
    execution_id: uuid.UUID,
    request: Request,
    tail: int | None = Query(None, ge=1),
    follow: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(Execution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")
    _check_visibility(row, current_user)

    if follow:
        return _follow_logs(execution_id, db)

    if row.log_ref is None:
        if row.status == ExecutionStatus.running:
            return Response(
                content='{"message": "logs not yet available"}',
                status_code=202,
                media_type="application/json",
            )
        return Response(status_code=204)

    log_text = await fetch_log(row.log_ref)
    if log_text is None:
        return Response(status_code=204)

    if tail is not None:
        lines = log_text.splitlines()
        log_text = "\n".join(lines[-tail:])

    return APIResponse(
        data={"execution_id": str(execution_id), "log": log_text},
        meta=_meta(request),
    )


def _follow_logs(execution_id: uuid.UUID, db: AsyncSession) -> StreamingResponse:
    """Return a streaming response that tails logs until the execution is terminal."""

    async def _generate():
        poll_interval = 2
        last_offset = 0
        while True:
            await db.refresh(await db.get(Execution, execution_id))
            row = await db.get(Execution, execution_id)
            if row is None:
                return

            if row.log_ref and row.log_ref.startswith("s3://"):
                # Yield any new bytes since last poll.
                chunks: list[bytes] = []
                async for chunk in stream_log(row.log_ref):
                    chunks.append(chunk)
                data = b"".join(chunks)
                if len(data) > last_offset:
                    yield data[last_offset:]
                    last_offset = len(data)

            if row.status in _TERMINAL:
                return

            await asyncio.sleep(poll_interval)

    return StreamingResponse(_generate(), media_type="text/plain")


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(Execution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")
    _check_visibility(row, current_user)

    if row.status in _TERMINAL:
        raise HTTPException(status_code=409, detail="execution already in terminal state")

    row.cancel_requested = True
    await update_execution_status(row, ExecutionStatus.cancelled, db)
    return APIResponse(data=ExecutionRead.model_validate(row), meta=_meta(request))


@router.get("/{execution_id}/wait")
async def wait_for_execution(
    execution_id: uuid.UUID,
    request: Request,
    timeout: int = Query(60, ge=1, le=300),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(Execution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")
    _check_visibility(row, current_user)

    elapsed = 0
    poll_interval = 2
    while row.status not in _TERMINAL and elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        await db.refresh(row)

    if row.status in _TERMINAL:
        return APIResponse(data=ExecutionRead.model_validate(row), meta=_meta(request))

    raise HTTPException(
        status_code=408,
        detail={
            "message": "execution did not reach terminal status within timeout",
            "execution": ExecutionRead.model_validate(row).model_dump(mode="json"),
        },
    )
