from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.http import FeanorHTTPClient
    from feanor.models.execution import Execution


class ExecutionsResource:
    def __init__(self, http: "FeanorHTTPClient") -> None:
        self._http = http

    async def list(self) -> list[Execution]:
        raise NotImplementedError

    async def get(self, execution_id: str) -> Execution:
        raise NotImplementedError

    async def submit(
        self,
        *,
        workflow: str,
        inputs: dict | None = None,
        wait: bool = False,
    ) -> Execution:
        raise NotImplementedError

    async def cancel(self, execution_id: str) -> None:
        raise NotImplementedError
