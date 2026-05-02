from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feanor.models.template import ExecutionTemplate


class TemplatesResource:
    """Implemented in task-008 / Phase 1."""

    def list(self) -> list[ExecutionTemplate]:
        raise NotImplementedError

    def get(self, template_id: str) -> ExecutionTemplate:
        raise NotImplementedError
