"""Connectors API — GET/POST/PATCH/DELETE /v1/connectors."""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db import get_db
from api.app.deps import ENGINEER, PLATFORM_ADMIN, CurrentUser, require_roles
from api.app.models.connector import Connector
from api.app.schemas import APIResponse, Meta
from api.app.schemas.connector import ConnectorCreate, ConnectorRead, ConnectorUpdate
from api.app.schemas.pagination import PaginatedMeta, decode_cursor, encode_cursor
from api.app.trino.catalog import remove_catalog, sync_catalog

router = APIRouter(prefix="/connectors", tags=["connectors"])

_ENG_OR_ADMIN = require_roles(ENGINEER, PLATFORM_ADMIN)
_ADMIN_ONLY = require_roles(PLATFORM_ADMIN)


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


def _encode_config(config: dict[str, Any] | None) -> bytes | None:
    if config is None:
        return None
    return json.dumps(config).encode("utf-8")


def _decode_config(raw: bytes | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    return json.loads(raw.decode("utf-8"))


def _to_read(conn: Connector) -> ConnectorRead:
    return ConnectorRead(
        id=conn.id,
        name=conn.name,
        type=conn.type,
        owner=conn.owner,
        config=_decode_config(conn.config_encrypted),
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.post("", status_code=201)
async def create_connector(
    body: ConnectorCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ENG_OR_ADMIN,
) -> Any:
    conn = Connector(
        id=uuid.uuid4(),
        name=body.name,
        type=body.type,
        config_encrypted=_encode_config(body.config),
        owner=current_user.subject,
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    await sync_catalog(conn)
    return APIResponse(data=_to_read(conn), meta=_meta(request))


@router.get("")
async def list_connectors(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    owner: str | None = Query(None),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ENG_OR_ADMIN,
) -> Any:
    stmt = select(Connector)

    if type:
        stmt = stmt.where(Connector.type == type)
    if owner:
        stmt = stmt.where(Connector.owner == owner)

    if cursor:
        try:
            cur_ts, cur_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid cursor")
        if order.lower() == "desc":
            stmt = stmt.where(
                or_(
                    Connector.created_at < cur_ts,
                    (Connector.created_at == cur_ts) & (Connector.id < cur_id),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    Connector.created_at > cur_ts,
                    (Connector.created_at == cur_ts) & (Connector.id > cur_id),
                )
            )

    if order.lower() == "desc":
        stmt = stmt.order_by(Connector.created_at.desc(), Connector.id.desc())
    else:
        stmt = stmt.order_by(Connector.created_at.asc(), Connector.id.asc())

    stmt = stmt.limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    total_q = select(func.count()).select_from(Connector)
    if type:
        total_q = total_q.where(Connector.type == type)
    if owner:
        total_q = total_q.where(Connector.owner == owner)
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


@router.get("/{connector_id}")
async def get_connector(
    connector_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ENG_OR_ADMIN,
) -> Any:
    row = await db.get(Connector, connector_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connector not found")
    return APIResponse(data=_to_read(row), meta=_meta(request))


@router.patch("/{connector_id}")
async def update_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ENG_OR_ADMIN,
) -> Any:
    row = await db.get(Connector, connector_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connector not found")

    if body.name is not None:
        row.name = body.name
    if body.config is not None:
        row.config_encrypted = _encode_config(body.config)

    await db.flush()
    await db.refresh(row)
    await sync_catalog(row)
    return APIResponse(data=_to_read(row), meta=_meta(request))


@router.delete("/{connector_id}", status_code=204)
async def delete_connector(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ADMIN_ONLY,
) -> None:
    row = await db.get(Connector, connector_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connector not found")
    await db.delete(row)
    await remove_catalog(row)
