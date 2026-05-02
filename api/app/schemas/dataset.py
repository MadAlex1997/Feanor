from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    source_ref: str
    schema_hints: dict[str, Any] | None = None
    lineage_refs: list[Any] | None = None


class DatasetUpdate(BaseModel):
    name: str | None = None
    schema_hints: dict[str, Any] | None = None
    lineage_refs: list[Any] | None = None


class DatasetRead(BaseModel):
    id: uuid.UUID
    name: str
    source_ref: str
    schema_hints: dict[str, Any] | None = None
    created_by: str
    lineage_refs: list[Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
