"""Shared async HTTP client — auth header injection and exponential-backoff retry."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from feanor.auth import TokenManager
from feanor.config import Profile
from feanor.exceptions import FeanorAPIError

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 503}
_MAX_RETRIES = 3
_BASE_DELAY = 1.0


class FeanorHTTPClient:
    """httpx.AsyncClient wrapper with automatic auth and retry."""

    def __init__(self, profile: Profile) -> None:
        self._profile = profile
        self._token_manager = TokenManager(profile)
        self._client = httpx.AsyncClient(
            base_url=profile.api_url,
            timeout=30.0,
        )

    async def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        token = self._token_manager.get_token()
        headers = dict(kwargs.pop("headers", {}))  # type: ignore[arg-type]
        headers["Authorization"] = f"Bearer {token}"

        delay = _BASE_DELAY
        for attempt in range(_MAX_RETRIES + 1):
            resp = await self._client.request(method, path, headers=headers, **kwargs)
            if resp.status_code not in _RETRY_STATUSES or attempt == _MAX_RETRIES:
                return resp
            logger.debug("Retrying after %s (attempt %d/%d, delay %.1fs)", resp.status_code, attempt + 1, _MAX_RETRIES, delay)
            await asyncio.sleep(delay)
            delay *= 2

        return resp  # unreachable, satisfies type checker

    async def get(self, path: str, **kwargs: object) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: object) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def patch(self, path: str, **kwargs: object) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: object) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    def raise_for_envelope(self, resp: httpx.Response) -> Any:
        """Parse the response envelope; raise FeanorAPIError on error or non-2xx."""
        if not resp.is_success:
            try:
                body = resp.json()
                msg = body.get("error") or body.get("detail") or resp.text
            except Exception:
                msg = resp.text
            raise FeanorAPIError(status_code=resp.status_code, message=str(msg))
        body = resp.json()
        if body.get("error"):
            raise FeanorAPIError(status_code=resp.status_code, message=body["error"])
        return body.get("data")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "FeanorHTTPClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
