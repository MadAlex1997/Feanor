"""Client — synchronous wrapper around AsyncClient."""
from __future__ import annotations

from feanor.async_client import AsyncClient


class Client:
    """Sync SDK client. Implemented in task-008."""

    def __init__(self) -> None:
        self._async = AsyncClient()
