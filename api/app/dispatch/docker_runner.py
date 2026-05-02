"""Docker-based local execution runner for all three template types."""
from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from api.app.dispatch import update_execution_status
from api.app.models.execution import Execution, ExecutionStatus
from api.app.storage import upload_log

if TYPE_CHECKING:
    from api.app.models.template import ExecutionTemplate

_DEFAULT_IMAGES = {
    "serverless_standard": "feanor-worker-serverless:local",
    "container_job_standard": "feanor-worker-container:local",
    "container_job_gpu": "feanor-worker-container:local",
}

_DEFAULT_TIMEOUT = {
    "serverless": 15 * 60,
    "container_job": 24 * 60 * 60,
    "distributed": 24 * 60 * 60,
}


def _get_image(template: "ExecutionTemplate") -> str | None:
    config = template.config or {}
    if "image" in config:
        return config["image"]
    return _DEFAULT_IMAGES.get(template.name)


def _get_timeout(template: "ExecutionTemplate") -> int:
    config = template.config or {}
    if "timeout" in config:
        return int(config["timeout"])
    return _DEFAULT_TIMEOUT.get(template.type.value, 15 * 60)


async def run_container(
    execution: Execution,
    template: "ExecutionTemplate",
    db: AsyncSession,
) -> None:
    """Run a worker container for the given execution."""
    import docker
    from docker.errors import DockerException, ImageNotFound

    if template.type.value == "distributed":
        await update_execution_status(
            execution,
            ExecutionStatus.failed,
            db,
            log_ref="inline:" + base64.b64encode(
                b"distributed template not supported in local MVP"
            ).decode(),
        )
        await db.commit()
        return

    image = _get_image(template)
    if image is None:
        await update_execution_status(
            execution,
            ExecutionStatus.failed,
            db,
            log_ref="inline:" + base64.b64encode(
                f"no image configured for template {template.name!r}".encode()
            ).decode(),
        )
        await db.commit()
        return

    timeout = _get_timeout(template)
    api_url = os.environ.get("FEANOR_API_URL", "http://api:8080")
    client_id = os.environ.get("FEANOR_DISPATCHER_CLIENT_ID", "")
    client_secret = os.environ.get("FEANOR_DISPATCHER_CLIENT_SECRET", "")
    s3_endpoint = os.environ.get("FEANOR_S3_ENDPOINT", "")
    result_prefix = os.environ.get("FEANOR_RESULT_PREFIX", "")
    network = os.environ.get("FEANOR_DOCKER_NETWORK", "feanor")

    env_vars = {
        "FEANOR_API_URL": api_url,
        "FEANOR_CLIENT_ID": client_id,
        "FEANOR_CLIENT_SECRET": client_secret,
        "FEANOR_EXECUTION_ID": str(execution.id),
        "FEANOR_INPUTS": json.dumps(execution.inputs or {}),
    }
    if s3_endpoint:
        env_vars["FEANOR_S3_ENDPOINT"] = s3_endpoint
    if result_prefix:
        env_vars["FEANOR_RESULT_PREFIX"] = result_prefix

    def _blocking_run() -> tuple[int, str]:
        cli = docker.from_env()
        container = cli.containers.run(
            image,
            detach=True,
            environment=env_vars,
            network=network,
        )
        poll_secs = 5
        elapsed = 0
        while elapsed < timeout:
            container.reload()
            if container.status == "exited":
                break
            # Check cancel_requested flag — reload from DB happens in caller
            if getattr(execution, "cancel_requested", False):
                container.kill()
                container.wait()
                return -1, "cancelled"
            asyncio.get_event_loop()
            elapsed += poll_secs
            import time
            time.sleep(poll_secs)
        else:
            container.kill()
            container.wait()
            return -1, "timeout"

        exit_code = container.attrs["State"]["ExitCode"]
        try:
            raw_logs = container.logs(tail=500)
            log_snippet = raw_logs[-500:] if len(raw_logs) > 500 else raw_logs
            log_text = log_snippet.decode("utf-8", errors="replace")
        except Exception:
            log_text = ""
        return exit_code, log_text

    try:
        exit_code, log_text = await asyncio.to_thread(_blocking_run)
    except ImageNotFound:
        log_msg = f"image not found: {image}"
        await update_execution_status(
            execution,
            ExecutionStatus.failed,
            db,
            log_ref="inline:" + base64.b64encode(log_msg.encode()).decode(),
        )
        await db.commit()
        return
    except DockerException as exc:
        log_msg = f"docker error: {exc}"
        await update_execution_status(
            execution,
            ExecutionStatus.failed,
            db,
            log_ref="inline:" + base64.b64encode(log_msg.encode()).decode(),
        )
        await db.commit()
        return

    # Upload logs to MinIO; fall back to inline if upload fails.
    log_ref: str | None = None
    if log_text:
        try:
            log_ref = await upload_log(execution.id, log_text.encode())
        except Exception:
            log_ref = "inline:" + base64.b64encode(log_text.encode()).decode()

    if exit_code == 0:
        await update_execution_status(
            execution, ExecutionStatus.succeeded, db, log_ref=log_ref
        )
    else:
        await update_execution_status(
            execution, ExecutionStatus.failed, db, log_ref=log_ref
        )
    await db.commit()
