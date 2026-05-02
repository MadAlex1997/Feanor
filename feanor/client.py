"""Client — synchronous wrapper around AsyncClient."""
from __future__ import annotations

import asyncio
from typing import Any

from feanor.async_client import AsyncClient


class Client:
    """Sync SDK client.

    Wraps AsyncClient so all methods are callable from synchronous code.
    Each method call creates a short-lived event loop via asyncio.run().
    """

    def __init__(self, profile: str | None = None) -> None:
        self._async = AsyncClient(profile)

    def __getattr__(self, name: str) -> Any:
        # Delegate attribute access to the underlying AsyncClient so that
        # resource namespaces (datasets, workflows, …) are accessible directly.
        return getattr(self._async, name)
