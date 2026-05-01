---
title: feanor Client and AsyncClient — HTTP client, retry logic, resource namespaces
phase: 0
status: Pending
---

## Description

Implement `feanor/async_client.py` (primary) and `feanor/client.py` (sync wrapper),
plus the shared HTTP layer in `feanor/http.py`. Resource namespace classes
(`datasets`, `workflows`, `executions`, `templates`, `system`) should be stubbed
with correct signatures but no real API calls — those are filled in during Phase 1.

The Phase 0 goal is: `client.system.health()` works end-to-end against the local stack.

## Acceptance criteria

- [ ] `AsyncClient` accepts no required arguments; resolves config from env / file / defaults.
- [ ] `AsyncClient` exposes five namespace attributes:
      `datasets`, `workflows`, `executions`, `templates`, `system` —
      each an instance of the corresponding resource class.
- [ ] `sync Client` wraps `AsyncClient` using `asyncio.run()` so all methods
      are callable from synchronous code.
- [ ] `feanor/http.py` provides a shared `httpx.AsyncClient` with:
      - Base URL from the active profile's `api_url`.
      - `Authorization: Bearer <token>` header injected on every request via
        the `TokenManager`.
      - Automatic retry with exponential backoff on `429` and `503`
        (max 3 retries, starting at 1 s).
- [ ] `client.system.health()` calls `GET /v1/system/health` and returns a
      typed Pydantic v2 `HealthResponse` model.
- [ ] All resource method stubs are typed (return type annotations, typed parameters)
      even if the body is `raise NotImplementedError`.
- [ ] `feanor system health` CLI command calls `client.system.health()` and
      prints the result as a table (using `rich`).
- [ ] Unit tests: retry logic (mock 429 → success), header injection, base URL resolution.

## Dependencies

- task-006 (package scaffold)
- task-007 (TokenManager must exist for header injection)
- task-009 (config loading must exist for profile resolution)
- task-003 (FastAPI `GET /health` must exist for the end-to-end smoke test)

## Notes

- `AsyncClient` is the single implementation; `Client` is a thin sync adapter.
  Do not duplicate HTTP logic.
- Pydantic v2 models in `feanor/models/` should mirror the API envelope:
  `DataResponse[T]` with `data: T`, `error: str | None`, `meta: dict`.
- The `system` resource namespace is the only one that needs a real implementation
  in Phase 0; everything else can be a stub.
- Output format flag (`--output table | json | yaml`) should be wired up in the
  CLI base, not per-command, so all commands get it for free in Phase 1.
