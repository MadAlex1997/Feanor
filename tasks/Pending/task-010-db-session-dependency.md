---
title: DB async session dependency and /v1 router prefix
phase: 1
status: Pending
---

## Description

Wire SQLAlchemy's async engine into the FastAPI app so route handlers can
receive a database session via dependency injection. Also establish the `/v1`
router prefix that all Phase 1 resource routes will live under.

## Acceptance criteria

- [ ] `api/app/db.py` exports:
      - `engine: AsyncEngine` created from `DATABASE_URL` env var.
      - `AsyncSessionLocal: async_sessionmaker[AsyncSession]`.
      - `get_db` FastAPI dependency (yields `AsyncSession`, commits on success,
        rolls back on exception, always closes).
- [ ] `api/app/main.py` mounts a `/v1` APIRouter; all Phase 1 resource routes
      will attach to this router.
- [ ] `GET /v1/` (or any sub-path) returns a meaningful 404, not a Traefik error,
      confirming the prefix is registered.
- [ ] The async engine uses `echo=False` in production; `echo=True` when
      `LOG_LEVEL=DEBUG` is set.
- [ ] Unit test: `get_db` rolls back and re-raises on exception, closes session
      in all cases.

## Dependencies

- task-003 (FastAPI app structure)
- task-004 (Alembic schema applied — tables exist before sessions query them)

## Notes

- Use `create_async_engine` from `sqlalchemy.ext.asyncio`. The URL scheme must
  be `postgresql+asyncpg://` — confirm the `DATABASE_URL` env var has this prefix.
- `async_sessionmaker` (not the deprecated `sessionmaker`) is the correct factory
  for SQLAlchemy 2.x async sessions.
- Do not call `Base.metadata.create_all()` from the app — migrations own the schema.
- The `/v1` prefix should be applied at the `APIRouter` level, not via `include_router`
  prefix argument on the app, so individual router files can be tested without the prefix.
