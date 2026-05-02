from __future__ import annotations

from typing import Any

from feanor.exceptions import FeanorAPIError
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

    async def submit(
        self,
        *,
        workflow: str,
        inputs: dict | None = None,
        wait: bool = False,
        timeout: int = 60,
        **kwargs: Any,
    ) -> Execution:
        # Resolve slug:version to a UUID if needed
        workflow_id = workflow
        if ":" in workflow:
            parts = workflow.split(":", 1)
            slug, version = parts[0], parts[1]
            from feanor.resources.workflows import WorkflowsResource

            wf_resource = WorkflowsResource(self._http)
            wf = await wf_resource.resolve(slug, version)
            workflow_id = str(wf.id)

        resp = await self._http.post(
            f"/v1/workflows/{workflow_id}/run",
            json={"inputs": inputs},
        )
        data = self._http.raise_for_envelope(resp)
        execution = Execution.model_validate(data)

        if not wait:
            return execution

        wait_resp = await self._http.get(
            f"/v1/executions/{execution.id}/wait",
            params={"timeout": timeout},
        )
        if wait_resp.status_code == 408:
            raise FeanorAPIError(408, "execution timed out waiting for terminal status")
        data = self._http.raise_for_envelope(wait_resp)
        return Execution.model_validate(data)

    async def cancel(self, execution_id: str) -> Execution:
        resp = await self._http.post(f"/v1/executions/{execution_id}/cancel")
        data = self._http.raise_for_envelope(resp)
        return Execution.model_validate(data)

    async def logs(
        self,
        execution_id: str,
        tail: int | None = None,
        follow: bool = False,
    ) -> str | None:
        params: dict[str, Any] = {}
        if tail is not None:
            params["tail"] = tail
        if follow:
            params["follow"] = "true"

        resp = await self._http.get(
            f"/v1/executions/{execution_id}/logs",
            params=params,
        )
        if resp.status_code in (202, 204):
            return None
        if follow:
            # Streaming response — return the full body as a string.
            return resp.text
        data = self._http.raise_for_envelope(resp)
        return data["log"]
