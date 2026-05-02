from __future__ import annotations

from typing import Any

from feanor.http import FeanorHTTPClient
from feanor.models.dataset import Dataset


class DatasetsResource:
    def __init__(self, http: FeanorHTTPClient) -> None:
        self._http = http

    async def list(self, **filters: Any) -> list[Dataset]:
        resp = await self._http.get("/v1/datasets", params={k: v for k, v in filters.items() if v is not None})
        data = self._http.raise_for_envelope(resp)
        return [Dataset.model_validate(item) for item in data]

    async def get(self, dataset_id: str) -> Dataset:
        resp = await self._http.get(f"/v1/datasets/{dataset_id}")
        data = self._http.raise_for_envelope(resp)
        return Dataset.model_validate(data)

    async def register(self, *, name: str, source: str, **kwargs: Any) -> Dataset:
        body: dict[str, Any] = {"name": name, "source_ref": source}
        if "schema_hints" in kwargs:
            body["schema_hints"] = kwargs["schema_hints"]
        if "lineage_refs" in kwargs:
            body["lineage_refs"] = kwargs["lineage_refs"]
        resp = await self._http.post("/v1/datasets", json=body)
        data = self._http.raise_for_envelope(resp)
        return Dataset.model_validate(data)

    async def update(self, dataset_id: str, **kwargs: Any) -> Dataset:
        resp = await self._http.patch(f"/v1/datasets/{dataset_id}", json=kwargs)
        data = self._http.raise_for_envelope(resp)
        return Dataset.model_validate(data)

    async def delete(self, dataset_id: str) -> None:
        resp = await self._http.delete(f"/v1/datasets/{dataset_id}")
        if resp.status_code == 204:
            return
        self._http.raise_for_envelope(resp)
