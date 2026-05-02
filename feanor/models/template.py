from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

TemplateType = Literal["serverless", "container_job", "distributed"]


class ExecutionTemplate(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    config: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
