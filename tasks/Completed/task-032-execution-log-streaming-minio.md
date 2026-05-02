---
title: Execution log streaming to MinIO
phase: 3
status: Pending
---

## Description

Phase 2 captured only the last 500 bytes of container output inline as
`log_ref: inline:<base64>`. This task replaces that with real log streaming to
MinIO. Workers stream stdout/stderr to a MinIO object as the container runs, and
`GET /v1/executions/{id}/logs` reads from MinIO — supporting both full retrieval
and a `--follow` live-tail mode.

## Acceptance criteria

### Dispatcher changes

- [ ] `api/app/dispatch/docker_runner.py` updated:
      - After starting the container, stream its logs to MinIO in a background
        coroutine using `asyncio.create_task`.
      - Log destination: `s3://feanor-logs/{execution_id}/stdout.log`
        (bucket name from `LOG_BUCKET` env var, default: `feanor-logs`).
      - Use `aioboto3` (or `boto3` via `asyncio.to_thread`) to upload.
      - Upload in chunks as the container emits output — do not buffer the full
        log in memory.
      - On container exit, finalize the upload (flush and close the stream).
      - Set `log_ref = f"s3://{LOG_BUCKET}/{execution_id}/stdout.log"` on the
        execution record on completion.

- [ ] `aioboto3` added to `[feature.api.dependencies]` in `pixi.toml`.

- [ ] `LOG_BUCKET` env var added to `docker-compose.yml` for the `api` service.
      MinIO bucket `feanor-logs` created in the MinIO init script (or on startup).

### Logs endpoint changes

- [ ] `GET /v1/executions/{id}/logs` extended:
      - If `log_ref` starts with `s3://`: stream the object from MinIO.
      - If `log_ref` starts with `inline:`: base64-decode and return as before
        (backwards compatibility for any Phase 2 executions).
      - If `log_ref` is null and the execution is `running`: return a
        `202 Accepted` with `{"message": "logs not yet available"}`.

- [ ] `GET /v1/executions/{id}/logs?follow=true` — live-tail mode:
      - Uses `StreamingResponse` (FastAPI).
      - Polls MinIO for new content every 2 seconds until the execution reaches
        a terminal status (`succeeded`, `failed`, `cancelled`).
      - Yields each new chunk as `text/plain` with no buffering.
      - Terminates the stream when the execution is terminal and no more bytes
        arrive after one final poll.

- [ ] `api/app/storage.py` — new module:
      - `async def stream_log(log_ref: str) -> AsyncIterator[bytes]`
        Routes to the right reader based on the `log_ref` prefix (`s3://` vs
        `inline:`).
      - `async def upload_log_stream(execution_id: UUID, source: AsyncIterator[bytes]) -> str`
        Uploads to MinIO and returns the `log_ref` string.

### SDK changes

- [ ] `feanor/resources/executions.py` — `logs(execution_id, follow=False)`:
      - `follow=False`: returns the full log as a single string.
      - `follow=True`: returns an iterator that yields log lines as they arrive
        (uses the `?follow=true` endpoint via chunked transfer).

### CLI changes

- [ ] `feanor executions logs <id>` prints full log.
- [ ] `feanor executions logs <id> --follow` streams live (already wired in
      task-026, but was no-op pending this task — make it functional).

### Tests

- [ ] Unit tests:
      - `stream_log("inline:<base64>")` returns the decoded bytes.
      - `stream_log("s3://...")` calls the MinIO reader.
      - `upload_log_stream(...)` calls the MinIO uploader with correct bucket/key.
- [ ] Integration test:
      - Submit an execution, wait for it to succeed, call `GET logs` and receive
        non-empty content.
      - `GET logs?follow=true` on a running execution returns a streaming response.

## Dependencies

- task-021 (Docker runner — log capture is currently inline 500 bytes)
- task-023 (logs endpoint exists — this extends it)
- task-028 (MinIO already running in Docker Compose)

## Notes

- MinIO bucket `feanor-logs` must be created at stack startup. Add it to the
  MinIO init script (or a `mc` container that runs `mc mb` on startup). If the
  bucket already exists, creation is a no-op.
- S3/MinIO credentials for the API service should use the same `MINIO_ROOT_USER`
  / `MINIO_ROOT_PASSWORD` env vars already in `.env`. Do not add new credentials.
- The `?follow=true` endpoint must handle the race condition where the execution
  finishes and the log upload completes between two polls. Check execution status
  after each poll; if terminal and no new bytes, close the stream.
- Chunked upload to MinIO requires multipart upload for large logs. Use the boto3
  multipart upload API or `aioboto3`'s equivalent. For logs under 5 MB (the MinIO
  minimum part size), a single-part upload is fine.
