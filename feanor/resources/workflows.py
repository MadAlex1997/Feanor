from __future__ import annotations

from typing import Any

from feanor.http import FeanorHTTPClient
from feanor.models.workflow import Workflow


class WorkflowsResource:
    def __init__(self, http: FeanorHTTPClient) -> None:
        self._http = http

    async def list(self, **filters: Any) -> list[Workflow]:
        resp = await self._http.get("/v1/workflows", params={k: v for k, v in filters.items() if v is not None})
        data = self._http.raise_for_envelope(resp)
        return [Workflow.model_validate(item) for item in data]

    async def get(self, workflow_id: str) -> Workflow:
        resp = await self._http.get(f"/v1/workflows/{workflow_id}")
        data = self._http.raise_for_envelope(resp)
        return Workflow.model_validate(data)

    async def create(self, *, slug: str, version: str, execution_template_id: str, **kwargs: Any) -> Workflow:
        body: dict[str, Any] = {
            "slug": slug,
            "version": version,
            "execution_template_id": execution_template_id,
        }
        if "definition" in kwargs:
            body["definition"] = kwargs["definition"]
        resp = await self._http.post("/v1/workflows", json=body)
        data = self._http.raise_for_envelope(resp)
        return Workflow.model_validate(data)

    async def update(self, workflow_id: str, **kwargs: Any) -> Workflow:
        resp = await self._http.patch(f"/v1/workflows/{workflow_id}", json=kwargs)
        data = self._http.raise_for_envelope(resp)
        return Workflow.model_validate(data)

    async def delete(self, workflow_id: str) -> None:
        resp = await self._http.delete(f"/v1/workflows/{workflow_id}")
        if resp.status_code == 204:
            return
        self._http.raise_for_envelope(resp)

    async def resolve(self, slug: str, version: str) -> Workflow:
        resp = await self._http.get(
            "/v1/workflows",
            params={"slug": slug, "limit": 1},
        )
        data = self._http.raise_for_envelope(resp)
        matches = [w for w in data if w.get("version") == version]
        if not matches:
            raise ValueError(f"workflow not found: {slug}:{version}")
        return Workflow.model_validate(matches[0])
