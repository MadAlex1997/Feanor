---
title: Connectors API — GET/POST/PATCH/DELETE /v1/connectors
phase: 1
status: Pending
---

## Description

Implement the connectors resource API. Connectors represent registered data
sources (PostgreSQL, MinIO/S3, HTTP APIs, etc.) and are the bridge between the
federated data access layer and the control plane. Connector config is stored
as plaintext for Phase 1 — encryption is deferred to Phase 6.

## Acceptance criteria

- [ ] `POST /v1/connectors` — register a connector.
      - Required body fields: `name: str`, `type: str` (e.g. `postgresql`, `s3`, `http`).
      - Optional: `config: dict | null` — source connection parameters.
      - `owner` is set from `CurrentUser.subject`.
      - Allowed roles: `engineer`, `platform_admin`.
      - Returns `201` with the created connector.
- [ ] `GET /v1/connectors` — list connectors.
      - Cursor-based pagination (`?cursor=&limit=`, default 20, max 100).
      - Filtering: `?type=<type>`, `?owner=<subject>`.
      - Allowed roles: `engineer`, `platform_admin`.
      - Analysts do NOT have list access to connectors (contain sensitive config).
- [ ] `GET /v1/connectors/{id}` — get a single connector.
      - Returns `404` if not found.
      - Allowed roles: `engineer`, `platform_admin`.
- [ ] `PATCH /v1/connectors/{id}` — update a connector.
      - Allowed fields: `name`, `config`.
      - `type` and `owner` are immutable.
      - Allowed roles: `engineer`, `platform_admin`.
- [ ] `DELETE /v1/connectors/{id}` — delete a connector.
      - Allowed roles: `platform_admin`.
      - Returns `204`.
- [ ] Pydantic schemas in `api/app/schemas/connector.py`:
      `ConnectorCreate`, `ConnectorUpdate`, `ConnectorRead`.
      `ConnectorRead` must OMIT the `config_encrypted` field — never expose raw
      config in responses. Use a `config: dict | null` field decoded from the DB.
- [ ] Route file: `api/app/routes/v1/connectors.py`.
- [ ] Unit tests: create, list (filtered by type), get (found + 404), update, delete.

## Dependencies

- task-010 (DB session)
- task-011 (role enforcement)

## Notes

- The `Connector` DB model stores config in `config_encrypted: LargeBinary`.
  For Phase 1, store config JSON bytes (UTF-8 encoded) directly — no actual
  encryption. The column name is kept for Phase 6 compatibility.
- Add a helper `_encode_config(config: dict | None) -> bytes | None` and
  `_decode_config(raw: bytes | None) -> dict | None` in the route file.
  When encryption is added (Phase 6), only these two functions change.
- Connector `type` is a free-form string in Phase 1. Known values:
  `postgresql`, `mysql`, `s3`, `gcs`, `http`, `file`. No enum enforcement
  yet — that comes with the Trino catalog wiring in Phase 3.
- Do not expose connector config to analysts — they query data through Trino,
  not by accessing connector credentials directly.
