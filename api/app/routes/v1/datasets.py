"""Datasets CRUD — POST/GET/PATCH/DELETE /v1/datasets."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db import get_db
from api.app.deps import ANALYST, ENGINEER, PLATFORM_ADMIN, CurrentUser, require_roles
from api.app.models.dataset import Dataset
from api.app.schemas import APIResponse, Meta
from api.app.schemas.dataset import DatasetCreate, DatasetRead, DatasetUpdate
from api.app.schemas.pagination import PaginatedMeta, decode_cursor, encode_cursor

router = APIRouter(prefix="/datasets", tags=["datasets"])

_ANY_ROLE = require_roles(ANALYST, ENGINEER, PLATFORM_ADMIN)
_ENG_OR_ADMIN = require_roles(ENGINEER, PLATFORM_ADMIN)
_ADMIN_ONLY = require_roles(PLATFORM_ADMIN)


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


@router.post("", status_code=201)
async def create_dataset(
    body: DatasetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    dataset = Dataset(
        id=uuid.uuid4(),
        name=body.name,
        source_ref=body.source_ref,
        schema_hints=body.schema_hints,
        lineage_refs=body.lineage_refs,
        created_by=current_user.subject,
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return APIResponse(data=DatasetRead.model_validate(dataset), meta=_meta(request))


@router.get("")
async def list_datasets(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    created_by: str | None = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ANY_ROLE,
) -> Any:
    stmt = select(Dataset)

    if created_by:
        stmt = stmt.where(Dataset.created_by == created_by)

    if cursor:
        try:
            cur_ts, cur_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid cursor")
        if order.lower() == "desc":
            stmt = stmt.where(
                or_(
                    Dataset.created_at < cur_ts,
                    (Dataset.created_at == cur_ts) & (Dataset.id < cur_id),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    Dataset.created_at > cur_ts,
                    (Dataset.created_at == cur_ts) & (Dataset.id > cur_id),
                )
            )

    if order.lower() == "desc":
        stmt = stmt.order_by(Dataset.created_at.desc(), Dataset.id.desc())
    else:
        stmt = stmt.order_by(Dataset.created_at.asc(), Dataset.id.asc())

    stmt = stmt.limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    total_q = select(func.count()).select_from(Dataset)
    if created_by:
        total_q = total_q.where(Dataset.created_by == created_by)
    total = (await db.execute(total_q)).scalar_one()

    return APIResponse(
        data=[DatasetRead.model_validate(r) for r in rows],
        meta=PaginatedMeta(
            request_id=request.state.request_id,
            cursor=next_cursor,
            limit=limit,
            total=total,
        ),
    )


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(Dataset, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return APIResponse(data=DatasetRead.model_validate(row), meta=_meta(request))


@router.patch("/{dataset_id}")
async def update_dataset(
    dataset_id: uuid.UUID,
    body: DatasetUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = _ANY_ROLE,
) -> Any:
    row = await db.get(Dataset, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="dataset not found")

    # Analysts may only update their own datasets
    is_privileged = ENGINEER in current_user.roles or PLATFORM_ADMIN in current_user.roles
    if not is_privileged and row.created_by != current_user.subject:
        raise HTTPException(status_code=403, detail="not the owner")

    if body.name is not None:
        row.name = body.name
    if body.schema_hints is not None:
        row.schema_hints = body.schema_hints
    if body.lineage_refs is not None:
        row.lineage_refs = body.lineage_refs

    await db.flush()
    await db.refresh(row)
    return APIResponse(data=DatasetRead.model_validate(row), meta=_meta(request))


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = _ADMIN_ONLY,
) -> None:
    row = await db.get(Dataset, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    await db.delete(row)
