from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class SystemResource:
    """Implemented in task-008."""

    def health(self) -> HealthResponse:
        raise NotImplementedError

    def ready(self) -> HealthResponse:
        raise NotImplementedError
