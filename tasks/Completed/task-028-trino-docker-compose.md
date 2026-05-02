---
title: Trino in Docker Compose — PostgreSQL and MinIO/S3 catalogs
phase: 3
status: Pending
---

## Description

Add Trino to the local MVP Docker Compose stack and configure it with two
catalogs: one pointing at the existing PostgreSQL service and one pointing at
MinIO (S3-compatible). This is the foundation for all federated query work in
Phase 3. No application code changes yet — this task is infrastructure only.

## Acceptance criteria

- [ ] `docker-compose.yml` updated with a `trino` service:
      - Image: `trinodb/trino:latest`
      - Port: `8080` mapped to host (or routed via Traefik as `/trino`)
      - Mounts a `./infra/trino/` config directory into `/etc/trino/`
      - Depends on `postgres` and `minio`
      - Health check: `GET http://localhost:8080/v1/info` returns `200`

- [ ] `infra/trino/config.properties` — coordinator config:
      ```
      coordinator=true
      node-scheduler.include-coordinator=true
      http-server.http.port=8080
      discovery.uri=http://localhost:8080
      ```

- [ ] `infra/trino/node.properties`:
      ```
      node.environment=local
      node.id=feanor-local-trino
      node.data-dir=/data/trino
      ```

- [ ] `infra/trino/jvm.config` — sensible defaults for local MVP (1–2 GB heap).

- [ ] `infra/trino/catalog/postgresql.properties` — PostgreSQL catalog:
      ```
      connector.name=postgresql
      connection-url=jdbc:postgresql://postgres:5432/feanor
      connection-user=${ENV:POSTGRES_USER}
      connection-password=${ENV:POSTGRES_PASSWORD}
      ```
      Credentials sourced from environment variables, not hardcoded.

- [ ] `infra/trino/catalog/minio.properties` — Hive connector targeting MinIO:
      ```
      connector.name=hive
      hive.metastore=file
      hive.metastore.catalog.dir=/data/trino-hive-catalog
      hive.s3.endpoint=http://minio:9000
      hive.s3.aws-access-key=${ENV:MINIO_ROOT_USER}
      hive.s3.aws-secret-key=${ENV:MINIO_ROOT_PASSWORD}
      hive.s3.path-style-access=true
      hive.s3.ssl.enabled=false
      ```

- [ ] `.env.example` updated with `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
      (already present from Phase 0 — confirm they are there, add if not).

- [ ] `docker compose up` starts successfully with Trino healthy.

- [ ] Manual smoke test documented in the task notes:
      - `docker exec -it feanor-trino-1 trino --catalog postgresql --schema public`
      - `SHOW TABLES;` returns the control plane tables.
      - `docker exec -it feanor-trino-1 trino --catalog minio`
      - `SHOW SCHEMAS;` returns without error (may be empty).

- [ ] `README.md` (top-level or `docs/local-stack.md`) updated with Trino
      access instructions and the two catalog names (`postgresql`, `minio`).

## Dependencies

- task-001 (Docker Compose stack — postgres and minio must be running)

## Notes

- Trino's file-based Hive metastore (`hive.metastore=file`) is sufficient for
  local MVP. It stores table metadata in a local directory on the Trino container.
  In production this would be replaced by a Glue or external Hive metastore.
- Do not add Trino to Traefik routing in this task — direct port exposure on
  `8080` is fine for MVP. Traefik integration can be added if needed in Phase 5.
- The `minio` catalog will be empty until a dataset is registered via the
  connector API (task-029). That is expected.
- Trino startup can be slow (30–60 seconds). Set `start_period: 60s` in the
  health check to avoid false negatives during `docker compose up`.
