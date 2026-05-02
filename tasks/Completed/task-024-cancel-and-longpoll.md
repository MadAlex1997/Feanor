---
title: "POST /v1/executions/{id}/cancel + GET /v1/executions/{id}/wait — cancel and long-poll"
phase: 2
status: Pending
---

## Description

Implement two remaining write-path execution endpoints. `POST /v1/executions/{id}/cancel`
lets callers abort a pending or running execution. `GET /v1/executions/{id}/wait`
is the server-side long-poll that `executions.submit(wait=True)` uses — it blocks
until the execution reaches a terminal status or the timeout expires, then returns
the final execution record.

## Acceptance criteria

- [ ] `POST /v1/executions/{id}/cancel`
      - No request body.
      - Valid only when `status` is `pending` or `running`. Returns `409` for
        any other current status with message "execution already in terminal state".
      - Sets `status = cancelled` and `ended_at = now()`.
      - For `running` executions: signals the dispatcher to stop the container.
        For local MVP, record the intent in the DB — the dispatcher's monitoring
        loop (task-021) polls for `cancelled` status and kills the container.
        Do not block the HTTP response on container teardown.
      - Returns `200` with the updated `ExecutionRead`.
      - Allowed roles: `analyst` (own executions only), `engineer`,
        `platform_admin`, `service_account`.
      - Returns `404` if execution not found; `403` if analyst tries to cancel
        another user's execution.

- [ ] `GET /v1/executions/{id}/wait`
      - Query parameter: `?timeout=<int, default 60, max 300>` seconds.
      - Polls the DB every 2 seconds until the execution status is one of
        `succeeded`, `failed`, `cancelled`, or the timeout elapses.
      - On terminal status: returns `200` with the final `ExecutionRead`.
      - On timeout: returns `408` (Request Timeout) with the current
        `ExecutionRead` in `data` and an error message.
      - Applies the same analyst visibility rules as `GET /v1/executions/{id}`.
      - Allowed roles: any authenticated user.

- [ ] Alembic migration `0005_add_execution_cancel_requested.py`:
      - Adds `cancel_requested: bool NOT NULL DEFAULT false` column to
        `executions`. The dispatcher (task-021) checks this flag to know
        when to kill a running container.

- [ ] Route additions in `api/app/routes/v1/executions.py`.

- [ ] Unit tests:
      - Cancel of `pending` execution returns 200 and sets `cancelled`.
      - Cancel of `succeeded` execution returns 409.
      - Analyst cannot cancel another user's execution (403).
      - `wait` returns immediately when execution is already terminal.
      - `wait` returns 408 after timeout (mock the polling loop).

## Dependencies

- task-020 (status transitions and `ExecutionStatusUpdate` schema)
- task-021 (dispatcher must check `cancel_requested` flag)
- task-014 (base route file and visibility helpers)

## Notes

- The long-poll loop uses `asyncio.sleep(2)` between DB polls. Do not use a
  fixed-interval busy loop — yield to the event loop between checks.
- `timeout` is server-enforced, not client-enforced. The client may set a
  longer HTTP timeout than the server's max (300 s) — the server returns 408
  before the client times out.
- For the cancel → container kill flow: the dispatcher's monitoring loop in
  task-021 must check `cancel_requested` after each Docker wait iteration
  (e.g. every 5 seconds) and call `container.kill()` if set. This avoids
  requiring a direct channel between the HTTP handler and the background task.
- `wait` is intentionally simple (DB polling, not SSE). Server-Sent Events
  would reduce DB load at scale but add implementation complexity not justified
  for the local MVP phase.
