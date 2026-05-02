---
title: Execution dispatcher — Docker-based local runner
phase: 2
status: Pending
---

## Description

Replace the no-op dispatcher stub from task-020 with a real Docker-based
dispatcher. For the local MVP, all three template types dispatch to Docker
containers. The dispatcher reads the execution record and its associated
template, selects the right container image, starts the container with the
correct environment, and monitors it to completion.

## Acceptance criteria

- [ ] `api/app/dispatch/docker_runner.py` exports:
      `async def run_container(execution: Execution, template: ExecutionTemplate) -> None`
      - Pulls (or assumes present) the worker image specified by the template config.
      - Starts the container with the following env vars injected:
        `FEANOR_API_URL`, `FEANOR_CLIENT_ID`, `FEANOR_CLIENT_SECRET`,
        `FEANOR_EXECUTION_ID`, `FEANOR_INPUTS` (JSON-encoded).
      - Waits for the container to exit (with a configurable timeout from the
        template config, defaulting to 15 minutes for serverless, 24h for container
        jobs).
      - On exit code 0: updates execution status to `succeeded` via
        `update_execution_status(...)` (direct DB write — not HTTP).
      - On non-zero exit code: updates status to `failed`, captures the last
        500 bytes of stdout+stderr as `log_ref` (stored inline as
        `inline:<base64>` for MVP; a real log store is Phase 3).
      - On timeout: kills the container and sets status to `failed`.

- [ ] `api/app/dispatch/__init__.py` exports:
      `async def dispatch_execution(execution_id: UUID, db: AsyncSession) -> None`
      - Loads the execution and its workflow+template.
      - Routes to `run_container` for all three template types in local MVP.
      - Sets `status = running` and `started_at = now()` before starting the container.
      - Catches all exceptions and sets `status = failed` with the exception
        message as `log_ref`.

- [ ] Template config key `image` specifies the Docker image to run. Default
      images per template (used when `image` is not set in config):
      - `serverless_standard`: `feanor-worker-serverless:local`
      - `container_job_standard` / `container_job_gpu`: `feanor-worker-container:local`
      - `distributed_spark_medium`: not supported locally — set status to `failed`
        with message "distributed template not supported in local MVP".

- [ ] Docker SDK dependency (`docker>=7`) added to `[feature.api.dependencies]`
      in `pixi.toml`.

- [ ] Unit tests (mocked Docker SDK):
      - Successful container run sets status to `succeeded`.
      - Non-zero exit sets status to `failed` with log captured.
      - Timeout kills container and sets status to `failed`.
      - Missing image raises `failed` (not an unhandled exception).

## Dependencies

- task-020 (dispatch stub and `update_execution_status` helper must exist)
- task-022 (worker images must exist to run end-to-end tests)

## Notes

- Use the `docker` Python SDK (`import docker`), not shell `subprocess`. The
  async wrapper is `asyncio.to_thread(blocking_docker_call)` — the Docker SDK
  is synchronous.
- The dispatcher must never let an exception propagate out of `dispatch_execution`
  — all failures must be recorded as `status = failed`. An unhandled exception
  would silently kill the background task with no trace in the execution record.
- `FEANOR_CLIENT_ID` and `FEANOR_CLIENT_SECRET` injected into the container must
  be a dedicated `dispatcher` service account in Keycloak with the `service_account`
  role. For local MVP, use the existing `FEANOR_DISPATCHER_CLIENT_ID` /
  `FEANOR_DISPATCHER_CLIENT_SECRET` env vars (added to Docker Compose in this task).
- Container networking: containers must be on the same Docker network as the API
  (`feanor_default`) so they can reach `http://api:8080` as `FEANOR_API_URL`.
- Log capture is intentionally minimal (last 500 bytes inline) for Phase 2.
  Full log streaming to MinIO is wired in Phase 3 when the object store connector lands.
