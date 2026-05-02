---
title: "GET /v1/executions/{id}/logs — execution log endpoint"
phase: 2
status: Pending
---

## Description

Implement `GET /v1/executions/{id}/logs`, which returns the log output for a
completed or running execution. For the local MVP, logs are stored as inline
base64 blobs in `log_ref` (format: `inline:<base64>`) or as files on the local
filesystem (`file:///path/to/log`). Phase 3 will add MinIO/S3 log retrieval.

## Acceptance criteria

- [ ] `GET /v1/executions/{id}/logs`
      - Path parameter: `execution_id: UUID`.
      - Query parameter: `?tail=<int>` — return only the last N lines
        (default: all lines).
      - Returns `200` with `{ "data": { "execution_id": "...", "log": "<text>" },
        "meta": { ... } }`.
      - Returns `404` if the execution does not exist.
      - Returns `204` (no content) if `log_ref` is null (logs not yet available).
      - Allowed roles: any authenticated user subject to the same visibility
        rules as `GET /v1/executions/{id}` (analysts only see own executions).

- [ ] Log source resolution (`api/app/dispatch/logs.py`):
      - `async def fetch_log(log_ref: str) -> str | None`
      - `inline:<base64>` → base64-decode and return as string.
      - `file://<path>` → read file from local filesystem asynchronously
        (`aiofiles`). Return `None` if file does not exist.
      - Unknown scheme → return `"<log source not supported: {scheme}>"`
        rather than raising.
      - `aiofiles` added to `[feature.api.dependencies]` in `pixi.toml`.

- [ ] The `?tail=N` parameter is applied after log fetching (split on newlines,
      take last N lines, rejoin). Applied client-side in the route handler, not
      in the log source — log sources always return the full log.

- [ ] Route added to `api/app/routes/v1/executions.py`.

- [ ] Unit tests:
      - `inline:` log ref decodes correctly.
      - `file://` log ref reads file content (mock `aiofiles.open`).
      - `?tail=5` returns only the last 5 lines.
      - Missing `log_ref` returns 204.
      - Analyst cannot see another user's execution logs (403).

## Dependencies

- task-020 (status update endpoint sets `log_ref` when execution fails/succeeds)
- task-022 (worker writes `log_ref` in `inline:` or `file://` format)
- task-014 (base executions route file and visibility rules)

## Notes

- Do NOT stream logs in Phase 2. Return the full log (or tailed version) as a
  single JSON response. Streaming via SSE is `feanor executions logs --follow`
  behaviour (task-026) and requires a different implementation path.
- `inline:<base64>` is the storage format used by the local dispatcher (task-021)
  for short container logs. It is intentionally limited to ~500 bytes to avoid
  bloating the DB. Full logs go to MinIO in Phase 3 when `log_ref` changes to an
  S3 URI.
- `file://` support exists for cases where the local dispatcher writes a log file
  to a shared volume. Use `FEANOR_LOG_DIR` env var (default `/tmp/feanor-logs`)
  as the base path.
- The `aiofiles` library handles async file reads without blocking the event loop.
  Add it to `pixi.toml` under `[feature.api.dependencies]`.
