---
title: Executions read API — GET /v1/executions, GET /v1/executions/{id}
phase: 1
status: Pending
---

## Description

Implement the read-only executions API. Execution records are created by
Phase 2's dispatch path (`POST /v1/workflows/{id}/run`). Phase 1 only needs
list and get — enough for scientists to check status after submissions are
wired in Phase 2.

## Acceptance criteria

- [ ] `GET /v1/executions` — list executions.
      - Cursor-based pagination (`?cursor=&limit=`, default 20, max 100).
      - Filtering: `?status=pending|running|succeeded|failed|cancelled`,
        `?workflow_id=<uuid>`.
      - Sorting: `?sort=created_at&order=asc|desc` (default: `created_at desc`).
      - Allowed roles: any authenticated user.
      - Analysts see only their own executions (filter by `created_by = subject`).
        Engineers and admins see all.
- [ ] `GET /v1/executions/{id}` — get a single execution by UUID.
      - Returns `404` if not found.
      - Visibility rule: analysts can only see their own; engineers and admins see all.
      - Allowed roles: any authenticated user.
- [ ] Pydantic schemas in `api/app/schemas/execution.py`:
      `ExecutionRead` (all fields including `status`, `inputs`, `result_ref`, `log_ref`).
- [ ] Route file: `api/app/routes/v1/executions.py`.
- [ ] Unit tests: list (filtered by status, by workflow_id), visibility scoping
      (analyst vs. engineer), get (found, 404, 403 for wrong analyst).

## Dependencies

- task-010 (DB session)
- task-011 (role enforcement)
- task-013 (workflows must exist before executions can reference them)

## Notes

- The `Execution` model does not have a `created_by` column yet. Add it in a
  new Alembic migration (`0003_add_execution_created_by.py`) before implementing
  the visibility scope filter. Column: `created_by VARCHAR NOT NULL DEFAULT ''`
  with a backfill or nullable initially if there is existing data.
- Write-path endpoints (`POST /v1/workflows/{id}/run`, cancel, logs) are Phase 2.
  Do not stub them here — the OpenAPI spec should only list implemented routes.
- The `status` filter should accept a comma-separated list:
  `?status=pending,running` to match multiple statuses in one query.
