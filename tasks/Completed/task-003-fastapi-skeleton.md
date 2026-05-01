---
title: FastAPI app skeleton — project structure, health endpoints, envelope middleware, OpenAPI spec
phase: 0
status: Completed
---

## Description

Create the `api/` directory containing the FastAPI control plane application.
This task covers the project scaffold, the two health endpoints, the response
envelope middleware, and OpenAPI spec configuration. No business-logic routes
are implemented here — that is Phase 1.

## Acceptance criteria

- [ ] `api/` directory contains the FastAPI app source; no separate `requirements.txt`
      or `pyproject.toml` — api dependencies are declared in the root `pixi.toml`
      under `[feature.api.dependencies]` (fastapi, uvicorn, sqlalchemy>=2, alembic,
      pydantic>=2, httpx, asyncpg).
- [ ] `pixi run api-dev` (defined in root `pixi.toml` `[tasks]`) starts the server
      with `uvicorn api.app.main:app --reload`.
- [ ] App entrypoint: `api/app/main.py` creates the FastAPI instance.
- [ ] `GET /health` returns `200` with `{ "data": { "status": "ok" }, "error": null, "meta": {} }`.
- [ ] `GET /ready` returns `200` when DB is reachable, `503` otherwise; same envelope.
- [ ] All responses use a consistent envelope:
      `{ "data": <payload>, "error": <str|null>, "meta": { "request_id": "..." } }`.
      Implemented as a response model base class or middleware — not duplicated per route.
- [ ] OpenAPI spec is served at `/openapi.json` and `/docs` (Swagger UI).
      Title: `Fëanor API`, version: `0.1.0`.
- [ ] A `Dockerfile` for the `api` service is added and the service is added to
      `docker-compose.yml`. The Dockerfile installs deps using the pinned
      `pixi.lock` (via `pixi install --frozen`) so dev and container envs are identical.
- [ ] Linting passes: `pixi run lint` (`black --check` and `ruff check`) with no errors.

## Dependencies

- task-001 (Postgres must be reachable for the `/ready` check)

## Notes

- Use `async def` for all route handlers from the start.
- The DB connection for `/ready` should be a simple `SELECT 1` — no ORM session needed.
- `request_id` in meta can be a UUID generated per request via middleware.
- Keep the app factory pattern in mind (`create_app()`) for easier testing later.
