"""Unit tests for feanor.resources.query (mocked httpx)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from feanor.config import Profile
from feanor.exceptions import FeanorQueryError
from feanor.resources.query import QueryResource, _extract_username

_PROFILE = Profile(
    name="test",
    api_url="http://localhost:8000",
    keycloak_url="http://localhost:8080",
    realm="feanor",
    trino_url="http://trino:8080",
    token=None,
)


def _resource() -> QueryResource:
    return QueryResource(_PROFILE)


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    return resp


# ---------------------------------------------------------------------------
# single-page response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_page_returns_rows() -> None:
    payload = {
        "id": "q123",
        "columns": [{"name": "n"}, {"name": "v"}],
        "data": [[1, "a"], [2, "b"]],
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(payload))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("feanor.resources.query.httpx.AsyncClient", return_value=mock_client):
        result = await _resource().query("SELECT 1")

    assert result.query_id == "q123"
    assert result.columns == ["n", "v"]
    assert result.rows == [{"n": 1, "v": "a"}, {"n": 2, "v": "b"}]


# ---------------------------------------------------------------------------
# multi-page (nextUri paging)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_page_accumulates_rows() -> None:
    first = {
        "id": "q1",
        "columns": [{"name": "x"}],
        "data": [[10]],
        "nextUri": "http://trino:8080/v1/statement/q1/1",
    }
    second = {
        "id": "q1",
        "data": [[20]],
        "nextUri": "http://trino:8080/v1/statement/q1/2",
    }
    third = {"id": "q1", "data": [[30]]}  # no nextUri — done

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(first))
    mock_client.get = AsyncMock(
        side_effect=[_mock_response(second), _mock_response(third)]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("feanor.resources.query.httpx.AsyncClient", return_value=mock_client):
        result = await _resource().query("SELECT x FROM t")

    assert result.rows == [{"x": 10}, {"x": 20}, {"x": 30}]


# ---------------------------------------------------------------------------
# Trino error response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trino_error_raises_query_error() -> None:
    payload = {
        "id": "q2",
        "error": {
            "message": "Table does not exist: foo.bar",
            "errorName": "TABLE_NOT_FOUND",
        },
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(payload))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("feanor.resources.query.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(FeanorQueryError) as exc_info,
    ):
        await _resource().query("SELECT * FROM foo.bar")

    assert "TABLE_NOT_FOUND" in str(exc_info.value)
    assert exc_info.value.error_name == "TABLE_NOT_FOUND"


# ---------------------------------------------------------------------------
# max_rows exceeded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_rows_exceeded_raises() -> None:
    first = {
        "id": "q3",
        "columns": [{"name": "n"}],
        "data": [[i] for i in range(5)],
        "nextUri": "http://trino:8080/v1/statement/q3/1",
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(first))
    mock_client.delete = AsyncMock(return_value=_mock_response({}, 204))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("feanor.resources.query.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(FeanorQueryError, match="more than 3 rows"),
    ):
        await _resource().query("SELECT n FROM t", max_rows=3)

    mock_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# HTTP error on submit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_error_raises() -> None:
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response({"error": "bad request"}, status_code=400)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("feanor.resources.query.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(FeanorQueryError, match="HTTP 400"),
    ):
        await _resource().query("BAD SQL")


# ---------------------------------------------------------------------------
# catalog / schema headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_schema_headers_sent() -> None:
    payload = {"id": "q4", "columns": [{"name": "n"}], "data": []}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(payload))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("feanor.resources.query.httpx.AsyncClient", return_value=mock_client):
        await _resource().query("SELECT 1", catalog="postgresql", schema="public")

    _, kwargs = mock_client.post.call_args
    headers = kwargs.get("headers", {})
    assert headers.get("X-Trino-Catalog") == "postgresql"
    assert headers.get("X-Trino-Schema") == "public"


# ---------------------------------------------------------------------------
# _extract_username
# ---------------------------------------------------------------------------


def test_extract_username_from_valid_jwt() -> None:
    import base64

    claims = {"preferred_username": "alice", "sub": "abc123"}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    token = f"header.{payload_b64}.sig"
    assert _extract_username(token) == "alice"


def test_extract_username_falls_back_on_invalid() -> None:
    assert _extract_username("not.a.token") == "feanor-sdk"
    assert _extract_username("") == "feanor-sdk"
