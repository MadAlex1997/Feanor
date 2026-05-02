---
title: Datasets CRUD API — POST/GET/PATCH/DELETE /v1/datasets
phase: 1
status: Pending
---

## Description

Implement the full datasets resource API. Datasets are the primary way scientists
register data sources for use in workflows. All endpoints live under `/v1/datasets`
and use the standard response envelope.

## Acceptance criteria

- [ ] `POST /v1/datasets` — create a dataset.
      - Required body fields: `name: str`, `source_ref: str`.
      - Optional: `schema_hints: dict | null`, `lineage_refs: list | null`.
      - `created_by` is set from `CurrentUser.subject` (not from the request body).
      - Allowed roles: `analyst`, `engineer`, `platform_admin`.
      - Returns `201` with the created dataset in the envelope.
- [ ] `GET /v1/datasets` — list datasets.
      - Cursor-based pagination: `?cursor=<opaque>&limit=<int, default 20, max 100>`.
      - Filtering: `?created_by=<subject>`.
      - Sorting: `?sort=created_at&order=asc|desc` (default: `created_at desc`).
      - Allowed roles: any authenticated user.
      - Returns paginated envelope: `{ "data": [...], "meta": { "cursor": "...", "total": N, ... } }`.
- [ ] `GET /v1/datasets/{id}` — get a single dataset by UUID.
      - Returns `404` with an error envelope if not found.
      - Allowed roles: any authenticated user.
- [ ] `PATCH /v1/datasets/{id}` — update a dataset.
      - Allowed fields: `name`, `schema_hints`, `lineage_refs`.
      - `source_ref` and `created_by` are immutable after creation.
      - Allowed roles: `engineer`, `platform_admin` (or the original `created_by` if analyst).
      - Returns the updated dataset.
- [ ] `DELETE /v1/datasets/{id}` — delete a dataset.
      - Allowed roles: `platform_admin`.
      - Returns `204` on success, `404` if not found.
- [ ] Pydantic v2 schemas live in `api/app/schemas/dataset.py`:
      `DatasetCreate`, `DatasetUpdate`, `DatasetRead`.
- [ ] Route file: `api/app/routes/v1/datasets.py`. Mounted on the `/v1` router.
- [ ] All endpoints appear in `GET /openapi.json`.
- [ ] Unit tests: create, list (pagination), get (found + 404), update, delete.

## Dependencies

- task-010 (DB session dependency)
- task-011 (role enforcement dependency)

## Notes

- Cursor is an opaque base64-encoded `created_at` + `id` pair — simple and
  stable under concurrent inserts. Do not use numeric offsets.
- `source_ref` should be stored as-is; no format validation at this layer.
- The `schema_hints` and `lineage_refs` fields are JSONB — pass through without
  schema enforcement.
- PATCH should use a Pydantic model with all fields optional (not a full replace).
- Use `select().where().limit().order_by()` with SQLAlchemy 2.x async session.
