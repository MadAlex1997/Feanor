from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

TemplateType = Literal["serverless", "container_job", "distributed"]


class TemplateCreate(BaseModel):
    name: str
    type: TemplateType
    config: dict[str, Any] | None = None


class TemplateRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    config: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
