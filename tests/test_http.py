"""Unit tests for feanor.http — retry logic and auth header injection."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from feanor.config import Profile, _DEFAULT_LOCAL
from feanor.http import FeanorHTTPClient


def _make_profile(**kwargs) -> Profile:
    return Profile(name="local", **{**_DEFAULT_LOCAL, **kwargs})


def _make_response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_auth_header_injected():
    profile = _make_profile()
    with patch("feanor.http.TokenManager") as MockTM:
        MockTM.return_value.get_token.return_value = "test-token"
        client = FeanorHTTPClient(profile)

        captured_headers = {}

        async def fake_request(method, path, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return _make_response(200, {"data": {"status": "ok"}})

        client._client.request = AsyncMock(side_effect=fake_request)
        await client.get("/health")

    assert captured_headers.get("Authorization") == "Bearer test-token"


@pytest.mark.asyncio
async def test_retry_on_429_then_success():
    profile = _make_profile()
    with patch("feanor.http.TokenManager") as MockTM:
        MockTM.return_value.get_token.return_value = "tok"
        client = FeanorHTTPClient(profile)

        call_count = 0

        async def fake_request(method, path, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return _make_response(429)
            return _make_response(200, {"data": "ok"})

        client._client.request = AsyncMock(side_effect=fake_request)

        with patch("feanor.http.asyncio.sleep", new_callable=AsyncMock):
            resp = await client.get("/v1/datasets")

    assert resp.status_code == 200
    assert call_count == 3


@pytest.mark.asyncio
async def test_gives_up_after_max_retries():
    profile = _make_profile()
    with patch("feanor.http.TokenManager") as MockTM:
        MockTM.return_value.get_token.return_value = "tok"
        client = FeanorHTTPClient(profile)

        client._client.request = AsyncMock(return_value=_make_response(503))

        with patch("feanor.http.asyncio.sleep", new_callable=AsyncMock):
            resp = await client.get("/v1/executions")

    # After MAX_RETRIES attempts, should return the last 503.
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_base_url_from_profile():
    profile = _make_profile(api_url="http://custom-host:9000")
    with patch("feanor.http.TokenManager") as MockTM:
        MockTM.return_value.get_token.return_value = "tok"
        client = FeanorHTTPClient(profile)

    assert str(client._client.base_url) == "http://custom-host:9000"
