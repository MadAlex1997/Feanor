from __future__ import annotations

from typing import Any

from feanor.http import FeanorHTTPClient
from feanor.models.execution import Execution


class ExecutionsResource:
    def __init__(self, http: FeanorHTTPClient) -> None:
        self._http = http

    async def list(self, **filters: Any) -> list[Execution]:
        resp = await self._http.get("/v1/executions", params={k: v for k, v in filters.items() if v is not None})
        data = self._http.raise_for_envelope(resp)
        return [Execution.model_validate(item) for item in data]

    async def get(self, execution_id: str) -> Execution:
        resp = await self._http.get(f"/v1/executions/{execution_id}")
        data = self._http.raise_for_envelope(resp)
        return Execution.model_validate(data)

    async def submit(self, *, workflow: str, inputs: dict | None = None, wait: bool = False, **kwargs: Any) -> Execution:
        raise NotImplementedError("execution submit is a Phase 2 feature")

    async def cancel(self, execution_id: str) -> None:
        raise NotImplementedError("execution cancel is a Phase 2 feature")
