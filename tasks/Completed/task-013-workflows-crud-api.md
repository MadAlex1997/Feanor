---
title: Workflows CRUD API — POST/GET/PATCH/DELETE /v1/workflows
phase: 1
status: Pending
---

## Description

Implement the workflows resource API. Workflows (also called algorithms) are
versioned definitions that declare an execution template and are submitted for
execution. Engineers own the lifecycle; scientists submit them for execution
(covered in Phase 2).

## Acceptance criteria

- [ ] `POST /v1/workflows` — create a workflow.
      - Required body fields: `slug: str`, `version: str`, `execution_template_id: uuid`.
      - Optional: `definition: dict | null`.
      - The `slug:version` pair must be unique — return `409` if it already exists.
      - `execution_template_id` must reference a valid template — return `422` if not.
      - Allowed roles: `engineer`, `platform_admin`.
      - Returns `201` with the created workflow.
- [ ] `GET /v1/workflows` — list workflows.
      - Cursor-based pagination (`?cursor=&limit=`, default 20, max 100).
      - Filtering: `?slug=<slug>`, `?execution_template_id=<uuid>`.
      - Sorting: `?sort=created_at|slug&order=asc|desc` (default: `created_at desc`).
      - Allowed roles: any authenticated user.
- [ ] `GET /v1/workflows/{id}` — get a single workflow by UUID.
      - Response includes the full `template` object (joined load), not just the ID.
      - Returns `404` if not found.
      - Allowed roles: any authenticated user.
- [ ] `PATCH /v1/workflows/{id}` — update a workflow.
      - Allowed fields: `definition`, `execution_template_id`.
      - `slug` and `version` are immutable after creation.
      - Allowed roles: `engineer`, `platform_admin`.
- [ ] `DELETE /v1/workflows/{id}` — delete a workflow.
      - Return `409` if any execution references this workflow (FK constraint).
      - Allowed roles: `platform_admin`.
      - Returns `204` on success.
- [ ] Pydantic schemas in `api/app/schemas/workflow.py`:
      `WorkflowCreate`, `WorkflowUpdate`, `WorkflowRead` (includes nested `TemplateRead`).
- [ ] Route file: `api/app/routes/v1/workflows.py`.
- [ ] Unit tests: create (duplicate slug returns 409, bad template_id returns 422),
      list, get (with template join), update, delete (blocked by FK returns 409).

## Dependencies

- task-010 (DB session)
- task-011 (role enforcement)
- task-015 (templates must exist in DB; seed data from migration 0002)

## Notes

- Workflow identity is `slug:version` (e.g. `my-etl-pipeline:v2`). The `id` is
  the DB primary key used in API paths; `slug:version` is the human-readable name.
- The FK constraint from `executions.workflow_id` means delete must handle the
  `ForeignKeyViolation` asyncpg exception and translate it to a `409`.
- The `definition` field is the algorithm's runtime specification (image, entrypoint,
  env vars, etc.). Schema validation of `definition` is the execution layer's job, not
  the control plane's.
- Joined load the template relationship on GET /{id} — avoid N+1 on list.
  For the list endpoint, include only `execution_template_id` (not the full template
  object) to keep list responses lean.
