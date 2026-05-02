from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.models.workflow import Workflow


class WorkflowsResource:
    """Implemented in task-008 / Phase 1."""

    def list(self) -> list[Workflow]:
        raise NotImplementedError

    def get(self, workflow_id: str) -> Workflow:
        raise NotImplementedError

    def create(self, **kwargs: object) -> Workflow:
        raise NotImplementedError

    def update(self, workflow_id: str, **kwargs: object) -> Workflow:
        raise NotImplementedError

    def delete(self, workflow_id: str) -> None:
        raise NotImplementedError
