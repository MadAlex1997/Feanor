from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.models.dataset import Dataset


class DatasetsResource:
    """Implemented in task-008 / Phase 1."""

    def list(self) -> list[Dataset]:
        raise NotImplementedError

    def get(self, dataset_id: str) -> Dataset:
        raise NotImplementedError

    def register(self, *, name: str, source: str, **kwargs: object) -> Dataset:
        raise NotImplementedError

    def update(self, dataset_id: str, **kwargs: object) -> Dataset:
        raise NotImplementedError

    def delete(self, dataset_id: str) -> None:
        raise NotImplementedError
