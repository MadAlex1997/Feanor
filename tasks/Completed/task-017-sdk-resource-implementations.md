---
title: SDK resource implementations — fill in all resource namespace stubs
phase: 1
status: Pending
---

## Description

Implement the real HTTP calls in each SDK resource namespace, replacing the
`raise NotImplementedError` stubs from task-006. Each method should call the
corresponding control plane endpoint, parse the response envelope, and return
a typed Pydantic v2 model. This task covers all five namespaces.

## Acceptance criteria

- [ ] `feanor/resources/datasets.py` — async methods:
      `list(**filters)`, `get(id)`, `register(name, source, **kwargs)`,
      `update(id, **kwargs)`, `delete(id)`.
      Returns `list[Dataset]` or `Dataset` as appropriate.
- [ ] `feanor/resources/workflows.py` — async methods:
      `list(**filters)`, `get(id)`, `create(slug, version, execution_template_id, **kwargs)`,
      `update(id, **kwargs)`, `delete(id)`.
- [ ] `feanor/resources/executions.py` — async methods:
      `list(**filters)`, `get(id)`.
      (`submit` and `cancel` remain `NotImplementedError` — Phase 2.)
- [ ] `feanor/resources/templates.py` — async methods:
      `list(**filters)`, `get(id)`, `create(name, type, **kwargs)`.
- [ ] `feanor/resources/system.py` — already implemented in task-008, no change needed.
- [ ] All methods raise `feanor.exceptions.FeanorAPIError` (new exception class)
      on non-2xx responses, including the API's error message from the envelope.
- [ ] `feanor/exceptions.py` defines `FeanorAPIError(Exception)` with `status_code`
      and `message` attributes.
- [ ] SDK Pydantic models in `feanor/models/` are updated to match the API schemas
      exactly (field names, types, optional fields).
- [ ] `AsyncClient` list methods support optional keyword filters that are passed
      as query parameters (e.g. `client.datasets.list(created_by="alice")`).
- [ ] Unit tests: mock `FeanorHTTPClient`, verify request path + method + body,
      verify response is correctly parsed into the Pydantic model.
      Test `FeanorAPIError` is raised on 404 and 403 responses.

## Dependencies

- task-012 (datasets API must exist to test against)
- task-013 (workflows API)
- task-014 (executions API)
- task-015 (templates API)
- task-016 (connectors API)

## Notes

- All resource methods are `async def`. The sync `Client` inherits them via
  `__getattr__` — callers using sync Client wrap with `asyncio.run()` themselves
  or use the async client in an event loop.
- The response envelope is `{ "data": ..., "error": ..., "meta": ... }`.
  Parse `data` for success, raise `FeanorAPIError` if `error` is set or status
  is not 2xx.
- List methods should return just the `data` list for simplicity in Phase 1.
  Pagination cursors will be exposed as a separate return value in Phase 2 when
  the CLI needs to implement `--all` page-through behaviour.
- Do not add a `connectors` resource to `AsyncClient` yet — connector management
  is an engineer/admin concern not exposed via the scientist-facing SDK in Phase 1.
  It can be added in Phase 6 if needed.
