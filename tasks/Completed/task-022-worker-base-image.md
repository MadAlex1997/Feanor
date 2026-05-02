---
title: Serverless worker base image and worker SDK
phase: 2
status: Pending
---

## Description

Build the Python base image that execution workers extend, and a concrete
`feanor-worker-serverless:local` image that implements the worker contract.
The worker SDK is a small Python library (`worker/sdk/`) that handles auth,
status reporting, and result writing — so individual algorithm containers need
only import it rather than re-implement the control plane integration.

## Acceptance criteria

- [ ] `worker/` directory structure:
      ```
      worker/
        sdk/
          __init__.py
          client.py      # WorkerClient — wraps feanor SDK for worker use
          context.py     # ExecutionContext — reads env vars, provides inputs
        serverless/
          Dockerfile
          entrypoint.py  # example no-op serverless algorithm
        container_job/
          Dockerfile
          entrypoint.py  # example no-op container job algorithm
      ```

- [ ] `worker/sdk/context.py` — `ExecutionContext`:
      - Reads from env vars: `FEANOR_API_URL`, `FEANOR_CLIENT_ID`,
        `FEANOR_CLIENT_SECRET`, `FEANOR_EXECUTION_ID`, `FEANOR_INPUTS`.
      - Exposes `.execution_id: str`, `.inputs: dict`, `.api_url: str`.
      - Validates all required env vars are present on construction; raises
        `EnvironmentError` with a clear message if any are missing.

- [ ] `worker/sdk/client.py` — `WorkerClient`:
      - Wraps `feanor.AsyncClient` (client credentials grant using
        `FEANOR_CLIENT_ID` / `FEANOR_CLIENT_SECRET`).
      - `async def report_running() -> None` — calls
        `PATCH /v1/executions/{id}/status` with `{"status": "running"}`.
      - `async def report_succeeded(result_ref: str) -> None` — calls status
        patch with `{"status": "succeeded", "result_ref": result_ref}`.
      - `async def report_failed(message: str) -> None` — calls status patch
        with `{"status": "failed", "log_ref": f"inline:{b64(message)}"}`.
      - `async def write_result(data: dict | str) -> str` — serialises result
        to JSON, writes to `FEANOR_RESULT_PREFIX/<execution_id>/result.json`
        via MinIO (using `boto3` with `endpoint_url = FEANOR_S3_ENDPOINT`).
        Returns the `result_ref` path. For MVP, falls back to writing a local
        file if `FEANOR_S3_ENDPOINT` is not set.

- [ ] `worker/serverless/Dockerfile`:
      - Base image: `python:3.11-slim`.
      - Installs `feanor` SDK from the local package (editable install or wheel).
      - Copies `worker/sdk/` and `worker/serverless/entrypoint.py`.
      - `CMD ["python", "entrypoint.py"]`.
      - Tagged as `feanor-worker-serverless:local` in `docker compose build`.

- [ ] `worker/serverless/entrypoint.py` (no-op example):
      ```python
      import asyncio
      from worker.sdk.context import ExecutionContext
      from worker.sdk.client import WorkerClient

      async def main():
          ctx = ExecutionContext()
          wc = WorkerClient(ctx)
          await wc.report_running()
          # algorithm body here — no-op for base image
          result_ref = await wc.write_result({"ok": True, "inputs": ctx.inputs})
          await wc.report_succeeded(result_ref)

      asyncio.run(main())
      ```

- [ ] `docker-compose.yml` updated:
      - Add `build` spec for `feanor-worker-serverless:local` under a `worker`
        service with `profiles: ["worker"]` so it is not started on
        `docker compose up` but is built on `docker compose build`.
      - Add `FEANOR_DISPATCHER_CLIENT_ID` and `FEANOR_DISPATCHER_CLIENT_SECRET`
        env vars to the `api` service.
      - Add `FEANOR_S3_ENDPOINT` and `FEANOR_RESULT_PREFIX` env vars to the
        dispatcher (api service) and worker containers.

- [ ] Unit tests for `ExecutionContext` (missing env vars raise correctly) and
      `WorkerClient` (mocked HTTP calls — verify correct path and payload for
      each report method).

## Dependencies

- task-020 (`PATCH /v1/executions/{id}/status` must exist for workers to call)
- task-021 (dispatcher must reference the correct image name)

## Notes

- The `feanor` SDK package installed in the worker image is the same package
  used by CLI users — no separate worker SDK package. The `worker/sdk/` helpers
  are thin wrappers on top of `feanor.AsyncClient` that read from env vars
  instead of `~/.feanor/config.yaml`.
- `write_result` in MVP uses boto3 pointed at MinIO. Do not hardcode bucket names —
  read from `FEANOR_RESULT_BUCKET` env var (default: `feanor-results`).
- The `container_job` Dockerfile and entrypoint mirror the serverless ones for Phase 2.
  Divergence (GPU, different base images) is a Phase 5 concern.
- Workers should exit with code 0 on success and non-zero on failure. The
  dispatcher (task-021) detects failure from the exit code, not from a status
  update call — so even if `report_failed` itself fails, the dispatcher catches
  the non-zero exit and records the failure.
