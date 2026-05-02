from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConnectorCreate(BaseModel):
    name: str
    type: str
    config: dict[str, Any] | None = None


class ConnectorUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None


class ConnectorRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    owner: str
    config: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}
