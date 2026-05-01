---
title: Docker Compose stack — Postgres, MinIO, Keycloak, Traefik
phase: 0
status: Completed
---

## Description

Create the `docker-compose.yml` that defines the full local MVP infrastructure.
This is the foundation all other Phase 0 tasks depend on. All services must come
up cleanly with a single `docker compose --project-name feanor up`.

Services to include:

| Service | Image | Purpose |
|---|---|---|
| `postgres` | `postgres:16` | Control plane DB + Airflow metadata DB |
| `minio` | `minio/minio` | S3-compatible object store |
| `keycloak` | `quay.io/keycloak/keycloak:23` | Identity provider (dev mode), realm: `feanor` |
| `traefik` | `traefik:v3` | API gateway / reverse proxy |

The `api` service (FastAPI) will be added in task-003 once the app skeleton exists.

## Acceptance criteria

- [ ] `docker compose --project-name feanor up` starts all four services without errors.
- [ ] Postgres is reachable on `localhost:5432` with a `feanor` database and user.
- [ ] MinIO console is reachable on `localhost:9001`; API on `localhost:9000`.
- [ ] Keycloak is reachable on `localhost:8080` in dev mode.
- [ ] Traefik dashboard is reachable on `localhost:8081`.
- [ ] A named volume or bind mount persists Postgres data across restarts.
- [ ] A `.env.example` documents all required environment variables (passwords, keys).
- [ ] Services use a shared Docker network named `feanor`.

## Dependencies

None — this is the root task for Phase 0.

## Notes

- Keycloak dev mode is acceptable for local MVP (no clustering, no TLS required).
- Use `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` env vars; do not hardcode credentials.
- Traefik config will be minimal here (just dashboard + Docker provider enabled);
  JWT routing and API forwarding are wired in task-005.
- Postgres init script should create the `feanor` database and role.

## Implementation notes

- Keycloak image tag is `23.0` (not `23` — that tag does not exist on quay.io).
- Keycloak uses Postgres as its backend (separate `keycloak` database); no separate
  data volume mount needed for Keycloak itself.
- Traefik listens on port **8000** (not 80) — port 80 was already in use on the
  host. This aligns with the `api_url: http://localhost:8000` local profile config.
- All bind-mount volumes land under `./volumes/` on the Data drive (`/Projects`).
