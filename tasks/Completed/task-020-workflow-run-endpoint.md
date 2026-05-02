---
title: "POST /v1/workflows/{id}/run — execution submission endpoint"
phase: 2
status: Pending
---

## Description

Implement `POST /v1/workflows/{id}/run`, the entry point for all execution
submissions. The endpoint creates an `Execution` record with status `pending`,
triggers an async dispatch background task, and immediately returns the new
execution record. Callers use `GET /v1/executions/{id}` to poll status.

Also add `PATCH /v1/executions/{id}/status` — a restricted endpoint used
exclusively by execution workers to report status transitions.

## Acceptance criteria

- [ ] `POST /v1/workflows/{id}/run`
      - Request body: `{ "inputs": dict | null }`.
      - Creates an `Execution` row: `status=pending`, `created_by` from caller,
        `inputs` from body, `started_at=null`.
      - Triggers `dispatch_execution(execution_id)` as a FastAPI `BackgroundTask`.
      - Returns `202` with the new `ExecutionRead` in the envelope.
      - Returns `404` if the workflow does not exist.
      - Allowed roles: `analyst`, `engineer`, `platform_admin`, `service_account`.

- [ ] `PATCH /v1/executions/{id}/status` — worker-only status update.
      - Request body: `{ "status": "running"|"succeeded"|"failed"|"cancelled",
        "result_ref": str | null, "log_ref": str | null }`.
      - Sets `started_at = now()` when transitioning to `running`.
      - Sets `ended_at = now()` when transitioning to a terminal status.
      - Allowed roles: `service_account` only.
      - Returns `200` with the updated `ExecutionRead`.
      - Returns `409` if the transition is invalid (e.g. `pending → succeeded`).

- [ ] Valid status transitions (enforced in code, not just DB):
      `pending → running`, `running → succeeded`, `running → failed`,
      `pending → cancelled`, `running → cancelled`.

- [ ] Pydantic schemas in `api/app/schemas/execution.py`:
      `ExecutionRunRequest`, `ExecutionStatusUpdate` (new).

- [ ] Route file: `api/app/routes/v1/executions.py` (extend existing).

- [ ] The dispatch function signature:
      `async def dispatch_execution(execution_id: uuid.UUID, db: AsyncSession) -> None`
      Lives in `api/app/dispatch/__init__.py`. In this task it is a no-op stub
      that immediately sets status to `running` then `succeeded` (to enable
      end-to-end smoke tests before task-021 lands).

- [ ] Unit tests: 202 on submit, 404 for missing workflow, valid/invalid status
      transitions, non-service-account rejected on status patch.

- [ ] Integration test: `POST /run` → `GET /{id}` shows `pending` (before
      background task runs) or `succeeded` (after).

## Dependencies

- task-014 (executions read API and model)
- task-013 (workflows must exist)
- task-011 (role enforcement — `service_account` role must be tested)

## Notes

- `BackgroundTasks` from FastAPI is the right primitive here. The dispatcher
  receives a DB session injected by its own `AsyncSessionLocal()` call — do not
  share the request session with the background task.
- The no-op dispatcher stub in this task must call `PATCH /v1/executions/{id}/status`
  via the DB directly (not via HTTP) to avoid a circular HTTP call during tests.
  The real Docker-based dispatcher (task-021) will use in-process DB writes too.
- Status transitions must be checked in the route handler before writing, not
  just at the DB constraint level. Return `409` with a meaningful message on
  invalid transitions.
- `service_account` is already defined as a role constant in `api/app/deps.py`.
