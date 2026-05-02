from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.http import FeanorHTTPClient
    from feanor.models.dataset import Dataset


class DatasetsResource:
    def __init__(self, http: "FeanorHTTPClient") -> None:
        self._http = http

    async def list(self) -> list[Dataset]:
        raise NotImplementedError

    async def get(self, dataset_id: str) -> Dataset:
        raise NotImplementedError

    async def register(self, *, name: str, source: str, **kwargs: object) -> Dataset:
        raise NotImplementedError

    async def update(self, dataset_id: str, **kwargs: object) -> Dataset:
        raise NotImplementedError

    async def delete(self, dataset_id: str) -> None:
        raise NotImplementedError
