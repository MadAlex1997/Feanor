---
title: SDK `client.query(sql)` method — Trino HTTP query
phase: 3
status: Pending
---

## Description

Add a `query(sql)` method to the SDK that executes a SQL statement against
Trino via the Trino HTTP API and returns results as a list of dicts. Both the
sync `Client` and the async `AsyncClient` must expose the method. This is the
primary interface scientists use to run federated queries without leaving Python.

## Acceptance criteria

- [ ] `feanor/resources/query.py` — new `QueryResource` (and `AsyncQueryResource`):
      - `def query(self, sql: str, catalog: str | None = None, schema: str | None = None) -> list[dict]`
      - `async def query(...)` async variant.
      - Uses the Trino HTTP API: `POST /v1/statement` to submit, then pages
        through `nextUri` links until the query completes.
      - Returns rows as `list[dict]` where keys are column names.
      - Raises `FeanorQueryError` (new exception class in `feanor/exceptions.py`)
        on Trino error responses, including the Trino `errorName` and `message`.
      - Respects `catalog` and `schema` parameters as `X-Trino-Catalog` and
        `X-Trino-Schema` headers.
      - Uses the same `httpx` client and retry logic as other SDK resources.
      - Passes the bearer token as `X-Trino-User` header (Trino uses this for
        identity; the actual JWT is passed as `Authorization: Bearer ...`).

- [ ] `feanor/models/query.py` — `QueryResult` Pydantic model:
      ```python
      class QueryResult(BaseModel):
          columns: list[str]
          rows: list[dict]
          query_id: str
          elapsed_ms: int
      ```
      `client.query(sql)` returns `QueryResult`.

- [ ] `AsyncClient` exposes `self.query` as an `AsyncQueryResource` instance.
      `Client` wraps it synchronously (same pattern as other resources).

- [ ] `FEANOR_TRINO_URL` env var (default: `http://localhost:8080`) controls
      which Trino endpoint the SDK targets. Loaded via `feanor/config.py` and
      settable per profile in `~/.feanor/config.yaml` as `trino_url`.

- [ ] Paging: `POST /v1/statement` returns a `nextUri`. The SDK must follow all
      `nextUri` links until the response has no `nextUri`, accumulating all row
      batches. Implement a configurable `max_rows` parameter (default: `10_000`)
      to prevent accidental full-table scans.

- [ ] Unit tests (mocked `httpx`):
      - Single-page response returns correct rows.
      - Multi-page response (two `nextUri` hops) accumulates all rows.
      - Trino error response raises `FeanorQueryError` with correct message.
      - `max_rows` exceeded raises `FeanorQueryError` with a descriptive message.

- [ ] Integration test (requires running Trino — skip if `TRINO_URL` not set,
      mark with `pytest.mark.integration`):
      - `client.query("SELECT 1 AS n")` returns `[{"n": 1}]`.
      - `client.query("SELECT * FROM postgresql.public.datasets LIMIT 5")`
        returns rows (may be empty, must not error).

## Dependencies

- task-028 (Trino running and accessible)
- task-009 (config loading — `trino_url` must be added to profile schema)
- task-017 (SDK resource pattern to follow)

## Notes

- Trino HTTP API overview: submit `POST /v1/statement` with `Content-Type: text/plain`
  and the SQL as the body. The response JSON contains `id`, `infoUri`, `nextUri`
  (if more data to fetch), and `data` (current batch of rows as `list[list]`).
  `columns` is present in the first response only. Subsequent `GET nextUri` calls
  return more `data` batches.
- Trino uses `X-Trino-User` (not `sub` from the JWT) for user identity in its
  query history. Set it to the authenticated user's username extracted from the
  token's `preferred_username` claim.
- Do not use `trino-python-client` (the official Trino Python driver). The HTTP
  API gives full control and avoids an additional heavy dependency. The paging
  logic is ~40 lines.
- `FeanorQueryError` should inherit from `FeanorError` (or a base exception class
  established in this task if one does not already exist in `feanor/exceptions.py`).
