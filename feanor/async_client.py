"""AsyncClient — primary SDK implementation."""
from __future__ import annotations

from __future__ import annotations

from feanor.config import Profile, load_config
from feanor.models.query import QueryResult
from feanor.http import FeanorHTTPClient
from feanor.resources.datasets import DatasetsResource
from feanor.resources.executions import ExecutionsResource
from feanor.resources.query import QueryResource
from feanor.resources.system import SystemResource
from feanor.resources.templates import TemplatesResource
from feanor.resources.workflows import WorkflowsResource


class AsyncClient:
    """Async SDK client.

    Reads credentials from environment variables or ~/.feanor/config.yaml.
    Falls back to device flow if no credentials are present.
    """

    def __init__(self, profile: str | None = None) -> None:
        self._resolved: Profile = load_config(profile)
        self._http = FeanorHTTPClient(self._resolved)

        self.datasets = DatasetsResource(self._http)
        self.workflows = WorkflowsResource(self._http)
        self.executions = ExecutionsResource(self._http)
        self.templates = TemplatesResource(self._http)
        self.system = SystemResource(self._http)
        self._query_resource = QueryResource(self._resolved)

    async def query(
        self,
        sql: str,
        *,
        catalog: str | None = None,
        schema: str | None = None,
        max_rows: int = 10_000,
    ) -> QueryResult:
        return await self._query_resource.query(sql, catalog=catalog, schema=schema, max_rows=max_rows)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
