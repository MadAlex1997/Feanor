"""Templates API — GET/POST /v1/templates (read-mostly, admin create)."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db import get_db
from api.app.deps import ANALYST, ENGINEER, PLATFORM_ADMIN, CurrentUser, require_roles
from api.app.models.template import ExecutionTemplate
from api.app.schemas import APIResponse, Meta
from api.app.schemas.pagination import PaginatedMeta, decode_cursor, encode_cursor
from api.app.schemas.template import TemplateCreate, TemplateRead

router = APIRouter(prefix="/templates", tags=["templates"])

_ANY_ROLE = require_roles(ANALYST, ENGINEER, PLATFORM_ADMIN)
_ADMIN_ONLY = require_roles(PLATFORM_ADMIN)


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


@router.get("")
async def list_templates(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    order: str = Query("asc"),
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ANY_ROLE,
) -> Any:
    stmt = select(ExecutionTemplate)

    if type:
        stmt = stmt.where(ExecutionTemplate.type == type)

    if cursor:
        try:
            cur_ts, cur_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid cursor")
        if order.lower() == "desc":
            stmt = stmt.where(
                or_(
                    ExecutionTemplate.created_at < cur_ts,
                    (ExecutionTemplate.created_at == cur_ts) & (ExecutionTemplate.id < cur_id),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    ExecutionTemplate.created_at > cur_ts,
                    (ExecutionTemplate.created_at == cur_ts) & (ExecutionTemplate.id > cur_id),
                )
            )

    if order.lower() == "desc":
        stmt = stmt.order_by(ExecutionTemplate.created_at.desc(), ExecutionTemplate.id.desc())
    else:
        stmt = stmt.order_by(ExecutionTemplate.created_at.asc(), ExecutionTemplate.id.asc())

    stmt = stmt.limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    total_q = select(func.count()).select_from(ExecutionTemplate)
    if type:
        total_q = total_q.where(ExecutionTemplate.type == type)
    total = (await db.execute(total_q)).scalar_one()

    return APIResponse(
        data=[TemplateRead.model_validate(r) for r in rows],
        meta=PaginatedMeta(
            request_id=request.state.request_id,
            cursor=next_cursor,
            limit=limit,
            total=total,
        ),
    )


@router.get("/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(ExecutionTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="template not found")
    return APIResponse(data=TemplateRead.model_validate(row), meta=_meta(request))


@router.post("", status_code=201)
async def create_template(
    body: TemplateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ADMIN_ONLY,
) -> Any:
    tmpl = ExecutionTemplate(
        id=uuid.uuid4(),
        name=body.name,
        type=body.type,
        config=body.config,
    )
    db.add(tmpl)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if "unique" in str(exc.orig).lower() or "uq_execution_templates_name" in str(exc.orig):
            raise HTTPException(status_code=409, detail="template name already exists")
        raise
    await db.refresh(tmpl)
    return APIResponse(data=TemplateRead.model_validate(tmpl), meta=_meta(request))
