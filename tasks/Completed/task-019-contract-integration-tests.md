---
title: Contract and integration tests for all Phase 1 endpoints
phase: 1
status: Pending
---

## Description

Write integration tests for every Phase 1 API endpoint. Tests spin up a real
PostgreSQL instance (via `testcontainers`) with migrations applied, inject
auth headers directly (bypassing Traefik), and assert against the full HTTP
response including envelope structure and status codes.

## Acceptance criteria

- [ ] `pixi run test` runs all unit and integration tests in a single command.
- [ ] Integration test fixture in `tests/conftest.py`:
      - Starts a PostgreSQL container (`testcontainers-python`).
      - Runs `alembic upgrade head` against it.
      - Provides an `AsyncClient` (httpx test client) wired to the FastAPI app
        with the test DB URL injected.
      - Yields auth headers for each role
        (`analyst_headers`, `engineer_headers`, `admin_headers`).
- [ ] `tests/integration/test_datasets.py`:
      - POST creates and returns a dataset (201).
      - GET list returns all datasets with pagination cursor.
      - GET by ID returns correct dataset (200), 404 on unknown ID.
      - PATCH updates allowed fields, rejects immutable fields.
      - DELETE returns 204, second DELETE returns 404.
      - Role checks: analyst can create; non-admin cannot delete (403).
- [ ] `tests/integration/test_workflows.py`:
      - POST creates workflow (201), duplicate slug:version returns 409.
      - Bad `execution_template_id` returns 422.
      - GET by ID includes the nested template object.
      - DELETE blocked by existing execution reference returns 409.
- [ ] `tests/integration/test_executions.py`:
      - List returns empty initially, returns seeded records after manual insert.
      - Status filter returns only matching records.
      - Analyst visibility scoping: only own executions returned.
- [ ] `tests/integration/test_templates.py`:
      - GET list returns the 4 seeded standard templates.
      - POST creates a new template (admin only); non-admin returns 403.
      - GET by ID returns correct template.
- [ ] `tests/integration/test_connectors.py`:
      - POST creates connector (engineer); analyst returns 403.
      - Config round-trips correctly (encode/decode).
      - GET list respects type filter.
- [ ] All Phase 1 endpoints are documented in `GET /openapi.json` (verified by
      parsing the spec in a test and asserting expected paths exist).

## Dependencies

- task-012 through task-016 (all API routes must be implemented)
- task-010 (DB session fixture depends on the engine setup)

## Notes

- Use `testcontainers` Python library (`testcontainers[postgres]`). Add to
  `[feature.dev.dependencies]` in `pixi.toml`.
- Do NOT mock the database in integration tests. The whole point is verifying
  the SQL and schema work end-to-end.
- Auth header injection: set `X-Feanor-Subject` and `X-Feanor-Roles` directly
  on the test client. The `require_roles` dependency reads these headers — no JWT
  needed in tests.
- Use `pytest-asyncio` (already in dev deps) with `asyncio_mode = "auto"` in
  `pytest.ini` or `pyproject.toml`.
- Mark integration tests with `@pytest.mark.integration` so they can be
  skipped in fast local runs: `pytest -m "not integration"`.
- The testcontainers fixture should be session-scoped to avoid spinning up a
  new container per test — use `@pytest.fixture(scope="session")`.
