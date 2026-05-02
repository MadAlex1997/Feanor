---
title: "SDK: executions.submit() with long-polling"
phase: 2
status: Pending
---

## Description

Implement `ExecutionsResource.submit()` on the Python SDK — the primary way
callers kick off a workflow execution. When `wait=True`, the method calls
`GET /v1/executions/{id}/wait` to block until the execution reaches a terminal
state and returns the final `Execution` model. When `wait=False` (default), it
returns immediately after the `POST /v1/workflows/{id}/run` response.

## Acceptance criteria

- [ ] `feanor/resources/executions.py` — `ExecutionsResource`:
      - `async def submit(self, workflow: str, inputs: dict | None = None, wait: bool = False, timeout: int = 60) -> Execution`
        - `workflow` accepts either a UUID string or a `slug:version` string
          (e.g. `"sales-etl:v3"`). If it is not a UUID, resolve it with
          `GET /v1/workflows?slug=<slug>&version=<version>` and extract the first
          result's `id`. Raise `ValueError` if no match is found.
        - Calls `POST /v1/workflows/{id}/run` with `{"inputs": inputs}`.
        - If `wait=False`: returns the `Execution` from the 202 response.
        - If `wait=True`: calls `GET /v1/executions/{id}/wait?timeout={timeout}`
          and returns the execution from the 200 response. On 408, raises
          `FeanorAPIError(408, "execution timed out waiting for terminal status")`.
      - `async def cancel(self, execution_id: str) -> Execution`
        - Calls `POST /v1/executions/{id}/cancel`.
        - Returns the updated `Execution`.
      - `async def logs(self, execution_id: str, tail: int | None = None) -> str | None`
        - Calls `GET /v1/executions/{id}/logs` (with `?tail=N` if provided).
        - Returns the log string, or `None` if the response is 204.

- [ ] `feanor/models/execution.py` — add `cancel_requested: bool` field
      (nullable for backwards compat; set to `False` if absent in response).

- [ ] Sync `Client` wrappers: `Client.executions.submit(...)` / `cancel(...)` /
      `logs(...)` — thin wrappers using `asyncio.run()` via the existing sync
      client pattern.

- [ ] `feanor/resources/workflows.py` — add `async def resolve(self, slug: str, version: str) -> Workflow`
      - Calls `GET /v1/workflows?slug={slug}&version={version}&limit=1`.
      - Returns the first result or raises `ValueError("workflow not found: {slug}:{version}")`.
      - Used by `executions.submit()` for the slug:version path.

- [ ] Unit tests (`tests/unit/test_executions_resource.py`):
      - `submit(wait=False)` calls POST run and returns immediately.
      - `submit(wait=True)` calls POST run then GET wait and returns terminal execution.
      - `submit(wait=True)` raises `FeanorAPIError(408, ...)` on 408 from wait endpoint.
      - `submit("slug:version", ...)` resolves to UUID before calling POST run.
      - `submit("non-existent:v1", ...)` raises `ValueError`.
      - `cancel(id)` calls POST cancel and returns updated execution.
      - `logs(id)` returns log string.
      - `logs(id)` returns `None` on 204.
      - `logs(id, tail=5)` appends `?tail=5` to the request.

## Dependencies

- task-020 (`POST /v1/workflows/{id}/run` must exist)
- task-024 (`GET /v1/executions/{id}/wait` and `POST /v1/executions/{id}/cancel`)
- task-023 (`GET /v1/executions/{id}/logs`)
- task-017 (existing `ExecutionsResource` stub to extend)

## Notes

- The `slug:version` resolution adds one extra GET per `submit()` call. This is
  acceptable for the common path (human callers using memorable names). UUID-based
  callers (Airflow DAGs, programmatic usage) pay zero overhead.
- `timeout` in `submit(wait=True, timeout=N)` is passed straight to the server's
  `?timeout=N` parameter. The SDK does not impose its own HTTP timeout on the
  long-poll — the server enforces the max (300 s). Callers who want a stricter
  client-side deadline should wrap in `asyncio.wait_for(...)`.
- `logs()` returning `None` for 204 (no logs yet) is the correct SDK contract.
  CLI commands that call it should print a message like "No logs available yet."
  rather than printing `None`.
- `cancel_requested` is an internal dispatcher field; the SDK model exposes it
  for completeness but callers should not rely on it for control flow.
