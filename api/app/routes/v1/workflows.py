"""Workflows CRUD — POST/GET/PATCH/DELETE /v1/workflows."""
from __future__ import annotations

import uuid
from typing import Any

from asyncpg import ForeignKeyViolationError, UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.app.db import get_db
from api.app.deps import ANALYST, ENGINEER, PLATFORM_ADMIN, CurrentUser, require_roles
from api.app.models.template import ExecutionTemplate
from api.app.models.workflow import Workflow
from api.app.schemas import APIResponse, Meta
from api.app.schemas.pagination import PaginatedMeta, decode_cursor, encode_cursor
from api.app.schemas.workflow import WorkflowCreate, WorkflowRead, WorkflowReadWithTemplate, WorkflowUpdate

router = APIRouter(prefix="/workflows", tags=["workflows"])

_ANY_ROLE = require_roles(ANALYST, ENGINEER, PLATFORM_ADMIN)
_ENG_OR_ADMIN = require_roles(ENGINEER, PLATFORM_ADMIN)
_ADMIN_ONLY = require_roles(PLATFORM_ADMIN)


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


def _to_read(wf: Workflow) -> WorkflowRead:
    return WorkflowRead.model_validate(wf)


def _to_read_with_template(wf: Workflow) -> WorkflowReadWithTemplate:
    from api.app.schemas.template import TemplateRead

    r = WorkflowReadWithTemplate.model_validate(wf)
    if wf.template is not None:
        r.template = TemplateRead.model_validate(wf.template)
    return r


@router.post("", status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ENG_OR_ADMIN,
) -> Any:
    # Validate template exists
    tmpl = await db.get(ExecutionTemplate, body.execution_template_id)
    if tmpl is None:
        raise HTTPException(status_code=422, detail="execution_template_id not found")

    wf = Workflow(
        id=uuid.uuid4(),
        slug=body.slug,
        version=body.version,
        execution_template_id=body.execution_template_id,
        definition=body.definition,
    )
    db.add(wf)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_workflows_slug_version" in str(exc.orig) or "unique" in str(exc.orig).lower():
            raise HTTPException(status_code=409, detail="slug:version already exists")
        raise
    await db.refresh(wf)
    return APIResponse(data=_to_read(wf), meta=_meta(request))


@router.get("")
async def list_workflows(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    slug: str | None = Query(None),
    execution_template_id: uuid.UUID | None = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ANY_ROLE,
) -> Any:
    stmt = select(Workflow)

    if slug:
        stmt = stmt.where(Workflow.slug == slug)
    if execution_template_id:
        stmt = stmt.where(Workflow.execution_template_id == execution_template_id)

    if cursor:
        try:
            cur_ts, cur_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid cursor")
        if order.lower() == "desc":
            stmt = stmt.where(
                or_(
                    Workflow.created_at < cur_ts,
                    (Workflow.created_at == cur_ts) & (Workflow.id < cur_id),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    Workflow.created_at > cur_ts,
                    (Workflow.created_at == cur_ts) & (Workflow.id > cur_id),
                )
            )

    if order.lower() == "desc":
        stmt = stmt.order_by(Workflow.created_at.desc(), Workflow.id.desc())
    else:
        stmt = stmt.order_by(Workflow.created_at.asc(), Workflow.id.asc())

    stmt = stmt.limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    total_q = select(func.count()).select_from(Workflow)
    if slug:
        total_q = total_q.where(Workflow.slug == slug)
    if execution_template_id:
        total_q = total_q.where(Workflow.execution_template_id == execution_template_id)
    total = (await db.execute(total_q)).scalar_one()

    return APIResponse(
        data=[_to_read(r) for r in rows],
        meta=PaginatedMeta(
            request_id=request.state.request_id,
            cursor=next_cursor,
            limit=limit,
            total=total,
        ),
    )


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ANY_ROLE,
) -> Any:
    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.template))
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return APIResponse(data=_to_read_with_template(row), meta=_meta(request))


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ENG_OR_ADMIN,
) -> Any:
    row = await db.get(Workflow, workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")

    if body.execution_template_id is not None:
        tmpl = await db.get(ExecutionTemplate, body.execution_template_id)
        if tmpl is None:
            raise HTTPException(status_code=422, detail="execution_template_id not found")
        row.execution_template_id = body.execution_template_id

    if body.definition is not None:
        row.definition = body.definition

    await db.flush()
    await db.refresh(row)
    return APIResponse(data=_to_read(row), meta=_meta(request))


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ADMIN_ONLY,
) -> None:
    row = await db.get(Workflow, workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        await db.delete(row)
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if "foreign key" in str(exc.orig).lower() or "fk" in str(exc.orig).lower():
            raise HTTPException(status_code=409, detail="workflow referenced by existing executions")
        raise
