from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.models.execution import Execution


class ExecutionsResource:
    """Implemented in task-008 / Phase 1."""

    def list(self) -> list[Execution]:
        raise NotImplementedError

    def get(self, execution_id: str) -> Execution:
        raise NotImplementedError

    def submit(self, *, workflow: str, inputs: dict | None = None, wait: bool = False) -> Execution:
        raise NotImplementedError

    def cancel(self, execution_id: str) -> None:
        raise NotImplementedError
