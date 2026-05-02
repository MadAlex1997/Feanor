"""WorkerClient — wraps feanor AsyncClient for use inside execution workers."""
from __future__ import annotations

import base64
import json
import os

import httpx

from worker.sdk.context import ExecutionContext


class WorkerClient:
    """Thin wrapper around the Feanor HTTP API for worker containers."""

    def __init__(self, ctx: ExecutionContext) -> None:
        self._ctx = ctx
        self._token: str | None = None

    async def _get_token(self) -> str:
        if self._token:
            return self._token
        # Client credentials grant
        keycloak_url = os.environ.get("FEANOR_KEYCLOAK_URL", "")
        realm = os.environ.get("FEANOR_KEYCLOAK_REALM", "feanor")
        token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._ctx.client_id,
                    "client_secret": self._ctx.client_secret,
                },
            )
            if resp.is_success:
                self._token = resp.json()["access_token"]
                return self._token
        # Fallback: use client_secret directly as a bearer token (dev/test mode)
        self._token = self._ctx.client_secret
        return self._token

    async def _patch_status(self, body: dict) -> None:
        token = await self._get_token()
        url = f"{self._ctx.api_url}/v1/executions/{self._ctx.execution_id}/status"
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()

    async def report_running(self) -> None:
        await self._patch_status({"status": "running"})

    async def report_succeeded(self, result_ref: str) -> None:
        await self._patch_status({"status": "succeeded", "result_ref": result_ref})

    async def report_failed(self, message: str) -> None:
        encoded = base64.b64encode(message.encode()).decode()
        await self._patch_status({"status": "failed", "log_ref": f"inline:{encoded}"})

    async def write_result(self, data: dict | str) -> str:
        """Serialise result and write to MinIO (or a local file fallback)."""
        payload = json.dumps(data) if not isinstance(data, str) else data

        s3_endpoint = os.environ.get("FEANOR_S3_ENDPOINT", "")
        bucket = os.environ.get("FEANOR_RESULT_BUCKET", "feanor-results")
        result_key = f"{self._ctx.execution_id}/result.json"

        if s3_endpoint:
            import boto3

            s3 = boto3.client(
                "s3",
                endpoint_url=s3_endpoint,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "changeme"),
            )
            s3.put_object(Bucket=bucket, Key=result_key, Body=payload.encode())
            return f"s3://{bucket}/{result_key}"

        # Local file fallback
        import aiofiles

        log_dir = os.environ.get("FEANOR_LOG_DIR", "/tmp/feanor-logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, f"{self._ctx.execution_id}_result.json")
        async with aiofiles.open(path, "w") as fh:
            await fh.write(payload)
        return f"file://{path}"
