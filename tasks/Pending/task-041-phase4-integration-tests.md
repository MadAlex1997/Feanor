---
title: Phase 4 integration tests — Airflow → control plane execution flow
phase: 4
status: Pending
---

## Description

Write the integration and end-to-end tests that prove Phase 4 is complete. The
canonical criterion from plan.md: a DAG runs on schedule (or on-trigger), submits
a workflow via the `feanor` SDK, and the execution record in the control plane
reflects the result. Tests are split into two layers: unit tests for the hook
and DAG logic (no Airflow runtime needed), and e2e tests that exercise the real
Airflow → control plane path via the Airflow REST API.

## Acceptance criteria

### Layer A — Unit tests (no running Airflow)

- [ ] `tests/test_airflow_hook.py` — tests for `FeanorHook` (already specified
      in task-038; confirm they exist and pass):
      - `get_client()` returns a `Client` with correct `api_url`.
      - Fallback to env vars when Airflow Connection extra fields are absent.

- [ ] `tests/test_airflow_dags.py` — DAG import and structure tests:
      - Import `dags/feanor_workflow_run.py` and `dags/feanor_data_validation.py`
        as Python modules (without an Airflow database).
      - Assert each DAG object has the expected `dag_id`, `schedule`, `tags`.
      - Assert each DAG has the expected task IDs.
      - No Airflow metadata DB required — use `dag.test()` in dry-run mode or
        just inspect the `dag.tasks` list.
      - These tests must pass in CI (without Docker Compose running).

- [ ] `tests/test_airflow_dags.py` uses `pytest.importorskip("airflow")` so the
      tests are skipped (not failed) when Airflow is not installed in the test env.

- [ ] `pixi.toml` updated: add `apache-airflow>=2.9` to a `[feature.airflow-tests]`
      optional feature so the dependency is only installed when running the
      Airflow test suite:
      ```toml
      [feature.airflow-tests.dependencies]
      apache-airflow = ">=2.9"
      ```

### Layer B — End-to-end tests (full Docker Compose stack)

These tests are marked `pytest.mark.e2e` and require the full stack to be up
(`docker compose up --wait`). They use the Airflow REST API to trigger DAGs.

- [ ] `tests/e2e/test_airflow_workflow_run.py`:

  - **Setup:** Ensure a test workflow exists in the control plane (call
    `POST /v1/workflows` via the `feanor` SDK if not already present).
    Set the Airflow Variable `feanor_workflow_run__workflow_slug` via the
    Airflow REST API:
    ```
    PATCH http://localhost:8081/api/v1/variables/feanor_workflow_run__workflow_slug
    Body: {"key": "...", "value": "<test-workflow-slug>"}
    ```

  - **Trigger:** `POST http://localhost:8081/api/v1/dags/feanor_workflow_run/dagRuns`
    with `{"conf": {}}`. Capture the `dag_run_id`.

  - **Poll:** Poll `GET /api/v1/dags/feanor_workflow_run/dagRuns/{dag_run_id}`
    every 5 seconds until `state` is `success` or `failed` (timeout: 120s).

  - **Assert:**
    - DAG run state is `success`.
    - At least one `Execution` record exists in the control plane (via
      `GET /v1/executions?limit=10`) with `status=succeeded`.
    - The execution's `created_by` matches the Airflow service account client ID.

- [ ] `tests/e2e/test_airflow_data_validation.py`:

  - **Setup:** Set Airflow Variable `feanor_data_validation__sql` to
    `"SELECT count(*) AS cnt FROM postgresql.public.workflows"` via the
    Airflow REST API. Set `min_rows` to `"0"` (no assumption on row count).

  - **Trigger + poll:** same pattern as above for `feanor_data_validation`.

  - **Assert:**
    - DAG run state is `success`.
    - All tasks in the run are in state `success`.

- [ ] `tests/e2e/conftest.py` extended with:
      - `airflow_api_client` fixture: an `httpx.Client` or `requests.Session`
        with `base_url="http://localhost:8081"` and basic auth
        `("admin", os.getenv("AIRFLOW_ADMIN_PASSWORD", "admin"))`.
      - `set_airflow_variable(key, value)` helper using the Airflow REST API.
      - `trigger_dag_run(dag_id) -> str` helper returning the `dag_run_id`.
      - `wait_for_dag_run(dag_id, dag_run_id, timeout=120) -> str` helper
        returning the final state.

### Test markers and CI

- [ ] `pytest.ini` (or `pyproject.toml`) already has the `e2e` marker from
      task-034. Confirm it is present; add a `airflow` sub-marker if desired:
      ```ini
      e2e: marks tests requiring the full Docker stack
      ```

- [ ] Running `pytest -m "not e2e"` passes without Airflow or Docker running.

- [ ] Running `pytest -m e2e tests/e2e/test_airflow_*.py` with the stack up
      passes all scenarios.

- [ ] `README.md` updated with instructions for running Phase 4 e2e tests,
      including how to set `AIRFLOW_ADMIN_PASSWORD` if changed from the default.

## Dependencies

- task-035 (Airflow in Docker Compose)
- task-036 (Keycloak service account)
- task-037 (Airflow image with feanor SDK)
- task-038 (FeanorHook)
- task-039 (workflow submission DAG)
- task-040 (data validation DAG)
- task-030 (SDK `client.query` — used by the validation DAG under test)
- task-020 (workflow run endpoint — executions must be submittable)

## Notes

- The Airflow REST API requires authentication. Basic auth with the admin
  credentials is simplest for testing. The Airflow API is enabled by default
  in Airflow 2.x; confirm `AIRFLOW__API__AUTH_BACKENDS` is set to
  `airflow.api.auth.backend.basic_auth` in the Docker Compose environment.
- The e2e tests for Layer B are intentionally slow (DAG runs take time).
  Do not add them to the default CI job. They belong in a separate
  `e2e` CI stage that runs `docker compose up --wait` first.
- When polling for DAG run completion, also check for `state = "failed"` and
  surface the failed task logs (via `GET /api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances`)
  to make test failure messages actionable.
- The test workflow used in Scenario A must actually exist and be dispatchable.
  Use the no-op stub dispatcher (from task-020) or ensure a real `container_job`
  worker is running. If the worker is not available, the execution will stay
  `pending` and the test will time out. Document this dependency clearly in
  test setup.
