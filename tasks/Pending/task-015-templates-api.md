---
title: Templates API — GET/POST /v1/templates
phase: 1
status: Pending
---

## Description

Implement the execution templates resource API. Templates are pre-seeded (four
standard ones from migration 0002) and mostly read-only. `platform_admin` users
can register custom templates for non-standard workloads.

## Acceptance criteria

- [ ] `GET /v1/templates` — list all templates.
      - Cursor-based pagination (`?cursor=&limit=`, default 20, max 100).
      - Filtering: `?type=serverless|container_job|distributed`.
      - Allowed roles: any authenticated user.
- [ ] `GET /v1/templates/{id}` — get a single template by UUID.
      - Returns `404` if not found.
      - Allowed roles: any authenticated user.
- [ ] `POST /v1/templates` — create a new template.
      - Required body fields: `name: str`, `type: serverless|container_job|distributed`.
      - Optional: `config: dict | null`.
      - `name` must be unique — return `409` if it already exists.
      - Allowed roles: `platform_admin` only.
      - Returns `201` with the created template.
- [ ] Pydantic schemas in `api/app/schemas/template.py`:
      `TemplateCreate`, `TemplateRead`.
- [ ] Route file: `api/app/routes/v1/templates.py`.
- [ ] Smoke test: `GET /v1/templates` returns the 4 seeded templates from migration
      0002 (`serverless_standard`, `container_job_standard`, `container_job_gpu`,
      `distributed_spark_medium`).
- [ ] Unit tests: list (with type filter), get (found + 404), create (duplicate
      name → 409, non-admin → 403).

## Dependencies

- task-010 (DB session)
- task-011 (role enforcement)
- task-004 (migration 0002 seeds the standard templates)

## Notes

- Templates are effectively configuration objects for the execution dispatcher
  (Phase 2). The `config` JSONB field holds template-specific parameters
  (memory limits, timeout, etc.) that the dispatcher reads.
- Do not allow `DELETE` or `PATCH` on templates in Phase 1 — template mutation
  could break existing workflows that reference them. That is a Phase 6 concern.
- The `name` field uses `snake_case` convention:
  `serverless_standard`, `container_job_gpu`, `distributed_spark_medium`.
