from __future__ import annotations

from typing import Any

from feanor.http import FeanorHTTPClient
from feanor.models.template import ExecutionTemplate


class TemplatesResource:
    def __init__(self, http: FeanorHTTPClient) -> None:
        self._http = http

    async def list(self, **filters: Any) -> list[ExecutionTemplate]:
        resp = await self._http.get("/v1/templates", params={k: v for k, v in filters.items() if v is not None})
        data = self._http.raise_for_envelope(resp)
        return [ExecutionTemplate.model_validate(item) for item in data]

    async def get(self, template_id: str) -> ExecutionTemplate:
        resp = await self._http.get(f"/v1/templates/{template_id}")
        data = self._http.raise_for_envelope(resp)
        return ExecutionTemplate.model_validate(data)

    async def create(self, *, name: str, type: str, **kwargs: Any) -> ExecutionTemplate:
        body: dict[str, Any] = {"name": name, "type": type}
        if "config" in kwargs:
            body["config"] = kwargs["config"]
        resp = await self._http.post("/v1/templates", json=body)
        data = self._http.raise_for_envelope(resp)
        return ExecutionTemplate.model_validate(data)
