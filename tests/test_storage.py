"""Unit tests for api.app.storage."""
from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.app.storage import read_log, stream_log, upload_log


# ---------------------------------------------------------------------------
# stream_log — inline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_log_inline() -> None:
    content = b"hello from inline log"
    encoded = base64.b64encode(content).decode()
    chunks: list[bytes] = []
    async for chunk in stream_log(f"inline:{encoded}"):
        chunks.append(chunk)
    assert b"".join(chunks) == content


# ---------------------------------------------------------------------------
# stream_log — s3://
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_log_s3() -> None:
    eid = uuid.uuid4()
    log_ref = f"s3://feanor-logs/{eid}/stdout.log"

    def _fake_s3():
        client = MagicMock()
        client.get_object.return_value = {"Body": MagicMock(read=lambda: b"log line\n")}
        return client

    with patch("api.app.storage._s3_client", _fake_s3):
        chunks: list[bytes] = []
        async for chunk in stream_log(log_ref):
            chunks.append(chunk)

    assert b"".join(chunks) == b"log line\n"


@pytest.mark.asyncio
async def test_stream_log_s3_missing_returns_empty() -> None:
    log_ref = "s3://feanor-logs/missing/stdout.log"

    def _fake_s3():
        client = MagicMock()
        client.get_object.side_effect = Exception("NoSuchKey")
        return client

    with patch("api.app.storage._s3_client", _fake_s3):
        chunks: list[bytes] = []
        async for chunk in stream_log(log_ref):
            chunks.append(chunk)

    assert chunks == []


@pytest.mark.asyncio
async def test_stream_log_unknown_scheme_yields_nothing() -> None:
    chunks: list[bytes] = []
    async for chunk in stream_log("gcs://bucket/key"):
        chunks.append(chunk)
    assert chunks == []


# ---------------------------------------------------------------------------
# upload_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_log_calls_put_object() -> None:
    eid = uuid.uuid4()

    def _fake_s3():
        client = MagicMock()
        return client

    with patch("api.app.storage._s3_client", _fake_s3) as mock_factory:
        log_ref = await upload_log(eid, b"some logs")

    assert log_ref.startswith("s3://")
    assert str(eid) in log_ref


# ---------------------------------------------------------------------------
# read_log convenience wrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_log_inline() -> None:
    text = "hello world"
    encoded = base64.b64encode(text.encode()).decode()
    result = await read_log(f"inline:{encoded}")
    assert result == text
