---
title: Phase 2 integration tests
phase: 2
status: Pending
---

## Description

End-to-end integration tests that verify the full Phase 2 execution pipeline:
submit a workflow, dispatch to a Docker container, poll for completion, retrieve
logs, and cancel a running execution. These tests require Docker (to actually run
worker containers) and the local stack (API + Postgres). They are marked
`@pytest.mark.integration` and `@pytest.mark.docker` to allow skipping in CI
environments without Docker.

## Acceptance criteria

- [ ] `tests/integration/test_execution_pipeline.py`:

  **Submit and wait (happy path)**
  - Register a `serverless_standard` template and a workflow pointing at it.
  - POST `/v1/workflows/{id}/run` with `{"inputs": {"echo": "hello"}}`.
  - GET `/v1/executions/{id}/wait?timeout=60` — assert status `succeeded` within
    60 seconds.
  - Assert `result_ref` is set and non-empty.

  **Submit and poll (manual polling)**
  - Submit a run; poll `GET /v1/executions/{id}` every 2 seconds until terminal
    or 30 seconds elapsed. Assert `succeeded`.
  - This validates the non-wait path without depending on the long-poll endpoint.

  **Long-poll timeout**
  - Submit a run that is guaranteed to take longer than the timeout (use a worker
    image or a mock that sleeps).
  - `GET /v1/executions/{id}/wait?timeout=5` — assert HTTP 408 and that the
    response body contains an `ExecutionRead` with status still `pending` or
    `running`.

  **Logs retrieval**
  - After a `succeeded` execution: GET `/v1/executions/{id}/logs` — assert HTTP
    200 and `data.log` is a non-empty string.
  - Assert that `?tail=1` returns exactly one line.

  **Logs not yet available**
  - GET `/v1/executions/{id}/logs` on an execution with `log_ref = null` — assert
    HTTP 204.

  **Cancel pending execution**
  - Submit a run and immediately POST `/v1/executions/{id}/cancel` before the
    dispatcher starts it (mock or pause the dispatcher).
  - Assert HTTP 200 and `data.status == "cancelled"`.
  - Assert `ended_at` is set.

  **Cancel running execution**
  - Submit a run against a long-running worker mock; wait for status `running`;
    POST cancel.
  - Assert HTTP 200 and `data.status == "cancelled"`.
  - Assert the Docker container is no longer running (poll `docker ps` or check
    via Docker SDK).

  **Cancel already-terminal execution**
  - POST cancel on a `succeeded` execution — assert HTTP 409 with message
    "execution already in terminal state".

  **Analyst visibility — logs and cancel**
  - Analyst submits own execution; confirm logs and cancel succeed (200).
  - Analyst attempts to cancel or retrieve logs for another user's execution;
    assert 403.

- [ ] `tests/integration/test_worker_client.py` (worker SDK integration):
  - Spin up the `feanor-worker-serverless:local` image directly (via Docker SDK).
  - Inject valid `FEANOR_API_URL`, `FEANOR_CLIENT_ID`, `FEANOR_CLIENT_SECRET`,
    `FEANOR_EXECUTION_ID`, `FEANOR_INPUTS`.
  - Verify it calls `PATCH /v1/executions/{id}/status` with `running`, then
    `succeeded`.
  - Verify `result_ref` is set on the execution after the container exits 0.

- [ ] `tests/integration/conftest.py` additions:
  - `docker_available` pytest mark auto-skip if Docker daemon is unreachable.
  - `worker_image` fixture: builds or tags `feanor-worker-serverless:local` using
    Docker SDK if not already present. Skip test if build fails.
  - `slow_worker_image` fixture: a minimal image (`python:3.11-slim`) that sleeps
    for 120 seconds — used for cancel and timeout tests. Built inline from a
    `Dockerfile` string using Docker SDK `BuildConfig`.

- [ ] All new tests marked with `@pytest.mark.integration` and
      `@pytest.mark.docker`. The `pixi.toml` test task should NOT include
      `--docker` by default; CI with Docker can pass `-m docker` explicitly.

- [ ] `pytest.ini` additions:
  - `docker: marks tests as requiring a running Docker daemon`

## Dependencies

- task-020 (`POST /run`, `PATCH /status`)
- task-021 (Docker dispatcher — must be running for container tests)
- task-022 (`feanor-worker-serverless:local` image)
- task-023 (logs endpoint)
- task-024 (cancel and long-poll endpoints)
- task-014 (execution visibility rules)

## Notes

- Use the existing `testcontainers` Postgres fixture from `tests/conftest.py` for
  the database; the API under test should point at the same container.
- The `api_client` fixture from Phase 1 tests uses the ASGI test client (no real
  network). Phase 2 Docker tests need a real running API server because worker
  containers call the API over HTTP. Start the FastAPI app on a random port using
  `uvicorn` in a background thread/process for the Docker tests.
- Worker containers must be on the same Docker network as the test-started API.
  Create a temporary Docker network in the `docker_available` or `api_server`
  fixture and pass it to `docker.containers.run(network=...)`.
- For the "cancel pending" test, pause the dispatcher by monkeypatching or by
  using a `serverless_standard` template with an image that does not exist —
  the dispatcher will fail to pull it, keeping the execution in `pending` long
  enough to cancel.
- Keep test timeouts short: `wait?timeout=10` for happy-path tests, `timeout=5`
  for the timeout test. Use `pytest-timeout` or asyncio timeouts on the test
  function itself to avoid hanging CI if something goes wrong.
- The `test_worker_client.py` tests run the actual worker image and verify the
  full round-trip (container → API → DB). They are slow (~10 s each) but are the
  canonical proof that the worker contract works end to end.
