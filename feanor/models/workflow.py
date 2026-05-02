from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class Workflow(BaseModel):
    id: uuid.UUID
    slug: str
    version: str
    definition: dict[str, Any] | None = None
    execution_template_id: uuid.UUID
