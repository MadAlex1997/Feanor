from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from feanor.http import FeanorHTTPClient


class HealthResponse(BaseModel):
    status: str


class SystemResource:
    def __init__(self, http: "FeanorHTTPClient") -> None:
        self._http = http

    async def health(self) -> HealthResponse:
        resp = await self._http.get("/health")
        resp.raise_for_status()
        data: Any = resp.json().get("data", {})
        return HealthResponse(status=data.get("status", "unknown"))

    async def ready(self) -> HealthResponse:
        resp = await self._http.get("/ready")
        resp.raise_for_status()
        data: Any = resp.json().get("data", {})
        return HealthResponse(status=data.get("status", "unknown"))
