from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.http import FeanorHTTPClient
    from feanor.models.workflow import Workflow


class WorkflowsResource:
    def __init__(self, http: "FeanorHTTPClient") -> None:
        self._http = http

    async def list(self) -> list[Workflow]:
        raise NotImplementedError

    async def get(self, workflow_id: str) -> Workflow:
        raise NotImplementedError

    async def create(self, **kwargs: object) -> Workflow:
        raise NotImplementedError

    async def update(self, workflow_id: str, **kwargs: object) -> Workflow:
        raise NotImplementedError

    async def delete(self, workflow_id: str) -> None:
        raise NotImplementedError
