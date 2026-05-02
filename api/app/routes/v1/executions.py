"""Executions read-only API — GET /v1/executions, GET /v1/executions/{id}."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db import get_db
from api.app.deps import ANALYST, ENGINEER, PLATFORM_ADMIN, CurrentUser, require_roles
from api.app.models.execution import Execution, ExecutionStatus
from api.app.schemas import APIResponse, Meta
from api.app.schemas.execution import ExecutionRead
from api.app.schemas.pagination import PaginatedMeta, decode_cursor, encode_cursor

router = APIRouter(prefix="/executions", tags=["executions"])

_ANY_ROLE = require_roles(ANALYST, ENGINEER, PLATFORM_ADMIN)


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


def _is_privileged(user: CurrentUser) -> bool:
    return ENGINEER in user.roles or PLATFORM_ADMIN in user.roles


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

    # Analysts only see their own executions
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

    if not _is_privileged(current_user) and row.created_by != current_user.subject:
        raise HTTPException(status_code=403, detail="not your execution")

    return APIResponse(data=ExecutionRead.model_validate(row), meta=_meta(request))
