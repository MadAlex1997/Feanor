"""Cursor-based pagination utilities shared across all list endpoints."""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class PaginatedMeta(BaseModel):
    request_id: str
    cursor: str | None = None
    limit: int
    total: int | None = None


def encode_cursor(created_at: datetime, id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(id_str)
    except Exception as exc:
        raise ValueError(f"invalid cursor: {exc}") from exc
