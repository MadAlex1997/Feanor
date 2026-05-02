from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.http import FeanorHTTPClient
    from feanor.models.template import ExecutionTemplate


class TemplatesResource:
    def __init__(self, http: "FeanorHTTPClient") -> None:
        self._http = http

    async def list(self) -> list[ExecutionTemplate]:
        raise NotImplementedError

    async def get(self, template_id: str) -> ExecutionTemplate:
        raise NotImplementedError
