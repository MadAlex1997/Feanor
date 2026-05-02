from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel

TemplateType = Literal["serverless", "container_job", "distributed"]


class ExecutionTemplate(BaseModel):
    id: uuid.UUID
    name: str
    type: TemplateType
    config: dict[str, Any] | None = None
