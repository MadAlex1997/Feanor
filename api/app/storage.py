"""MinIO / S3 object storage helpers for log and result blobs."""
from __future__ import annotations

import asyncio
import base64
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    pass

_ENDPOINT = os.environ.get("FEANOR_S3_ENDPOINT", "http://minio:9000")
_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER", "minioadmin")
_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "changeme")
_LOG_BUCKET = os.environ.get("LOG_BUCKET", "feanor-logs")


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
        region_name="us-east-1",
    )


def _log_key(execution_id: uuid.UUID) -> str:
    return f"{execution_id}/stdout.log"


def _log_ref(execution_id: uuid.UUID) -> str:
    return f"s3://{_LOG_BUCKET}/{_log_key(execution_id)}"


async def upload_log(execution_id: uuid.UUID, content: bytes) -> str:
    """Upload log bytes to MinIO and return the s3:// log_ref.

    Uses asyncio.to_thread so the blocking boto3 call doesn't block the event loop.
    """
    key = _log_key(execution_id)

    def _put() -> None:
        client = _s3_client()
        client.put_object(
            Bucket=_LOG_BUCKET,
            Key=key,
            Body=content,
            ContentType="text/plain",
        )

    await asyncio.to_thread(_put)
    return _log_ref(execution_id)


async def stream_log(log_ref: str) -> AsyncIterator[bytes]:
    """Yield bytes from a log_ref.

    Supported schemes:
      s3://<bucket>/<key>   — download from MinIO/S3
      inline:<base64>       — decode inline payload
    """
    if log_ref.startswith("inline:"):
        encoded = log_ref[len("inline:"):]
        yield base64.b64decode(encoded)
        return

    if log_ref.startswith("s3://"):
        # Parse s3://bucket/key
        rest = log_ref[len("s3://"):]
        bucket, _, key = rest.partition("/")

        def _get() -> bytes:
            client = _s3_client()
            resp = client.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()

        try:
            data = await asyncio.to_thread(_get)
            yield data
        except Exception:
            # Object may not exist yet (e.g. log not yet uploaded).
            return

    # Unknown scheme — yield nothing.


async def read_log(log_ref: str) -> str:
    """Convenience wrapper: read all log bytes and return as a string."""
    chunks: list[bytes] = []
    async for chunk in stream_log(log_ref):
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")
