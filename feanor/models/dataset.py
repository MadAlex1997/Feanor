from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Dataset(BaseModel):
    id: uuid.UUID
    name: str
    source_ref: str
    schema_hints: dict[str, Any] | None = None
    created_by: str
    lineage_refs: list[Any] | None = None
    created_at: datetime
    updated_at: datetime
