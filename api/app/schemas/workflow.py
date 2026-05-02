from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from api.app.schemas.template import TemplateRead


class WorkflowCreate(BaseModel):
    slug: str
    version: str
    execution_template_id: uuid.UUID
    definition: dict[str, Any] | None = None


class WorkflowUpdate(BaseModel):
    definition: dict[str, Any] | None = None
    execution_template_id: uuid.UUID | None = None


class WorkflowRead(BaseModel):
    id: uuid.UUID
    slug: str
    version: str
    definition: dict[str, Any] | None = None
    execution_template_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowReadWithTemplate(WorkflowRead):
    template: TemplateRead | None = None
