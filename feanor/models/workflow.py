from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from feanor.models.template import ExecutionTemplate


class Workflow(BaseModel):
    id: uuid.UUID
    slug: str
    version: str
    definition: dict[str, Any] | None = None
    execution_template_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    template: ExecutionTemplate | None = None
