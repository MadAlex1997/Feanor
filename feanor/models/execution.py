from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

ExecutionStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class Execution(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: ExecutionStatus
    inputs: dict[str, Any] | None = None
    result_ref: str | None = None
    log_ref: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
