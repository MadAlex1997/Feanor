---
title: Connector registration wired to Trino catalog config
phase: 3
status: Pending
---

## Description

When a connector is registered via `POST /v1/connectors`, the control plane must
generate (or update) the corresponding Trino catalog properties file and signal
Trino to reload it. When a connector is deleted, the catalog file must be removed.

This closes the loop between the connector metadata stored in Postgres (task-016)
and the live Trino instance that scientists query.

## Acceptance criteria

- [ ] `api/app/trino/catalog.py` module with:
      - `async def sync_catalog(connector: Connector) -> None`
        - Generates a `.properties` file in the Trino catalog dir based on
          connector type and config.
        - Writes to the path configured in `TRINO_CATALOG_DIR` env var
          (default: `/etc/trino/catalog` — the Docker bind-mount path).
        - Triggers a Trino catalog reload (see Notes).
      - `async def remove_catalog(connector: Connector) -> None`
        - Deletes the `.properties` file for the given connector.
        - Triggers a Trino catalog reload.
      - `def render_catalog_properties(connector: Connector) -> str`
        - Pure function — returns the `.properties` file content as a string.
        - Handles connector types: `postgresql`, `mysql`, `s3` (→ `hive`), `http`.
        - Raises `ValueError` for unsupported types with a clear message.

- [ ] `POST /v1/connectors` calls `sync_catalog(connector)` after DB commit.

- [ ] `DELETE /v1/connectors/{id}` calls `remove_catalog(connector)` after DB
      delete. Returns `404` if the connector does not exist.

- [ ] `PATCH /v1/connectors/{id}` calls `sync_catalog(connector)` after update
      (connector config may include new credentials).

- [ ] Connector `config` field credential values are stored encrypted at rest
      using `cryptography.fernet`. Key sourced from `FEANOR_SECRET_KEY` env var.
      `api/app/crypto.py` provides `encrypt(value: str) -> str` and
      `decrypt(value: str) -> str` helpers.

- [ ] `cryptography` added to `[feature.api.dependencies]` in `pixi.toml`.

- [ ] `TRINO_CATALOG_DIR` env var added to `docker-compose.yml` for the `api`
      service, pointing at the shared volume mount used by the `trino` service.

- [ ] Connector type → Trino connector name mapping:

      | Fëanor type | Trino connector |
      |---|---|
      | `postgresql` | `postgresql` |
      | `mysql` | `mysql` |
      | `s3` | `hive` (file metastore, MinIO-compatible) |
      | `http` | `http` (third-party or no-op if unsupported) |

- [ ] Unit tests:
      - `render_catalog_properties` produces correct content for each supported type.
      - Unsupported type raises `ValueError`.
      - `sync_catalog` writes the file to the expected path.
      - `remove_catalog` deletes the file.

- [ ] Integration test:
      - `POST /v1/connectors` with a `postgresql` type creates the catalog file.
      - `DELETE /v1/connectors/{id}` removes it.

## Dependencies

- task-016 (connectors CRUD API and DB model)
- task-028 (Trino running in Docker Compose with the catalog directory mounted)

## Notes

- **Trino catalog reload:** Trino supports dynamic catalog reload via
  `POST http://trino:8080/v1/catalog` (Trino 435+) or by restarting the service.
  For local MVP, write the catalog file and call
  `POST http://{TRINO_HOST}:8080/v1/catalog` with the catalog name. If the Trino
  version does not support it, fall back to logging a warning — the operator can
  restart Trino manually. Do not hard-fail the connector registration if Trino is
  unreachable; the connector record must still be saved.
- Credential values written to `.properties` files must be the decrypted
  plaintext — Trino reads them directly. Encryption only applies to values stored
  in Postgres.
- The `config` field on the `Connector` model is a `dict`. Store it as `JSONB` in
  Postgres (already the case from task-016). The catalog renderer picks named keys
  (`host`, `port`, `database`, `user`, `password`, `endpoint`, etc.).
- For `s3` connectors, the rendered `hive` catalog must include:
  `hive.s3.endpoint`, `hive.s3.path-style-access=true`, `hive.s3.ssl.enabled=false`
  for MinIO compatibility.
