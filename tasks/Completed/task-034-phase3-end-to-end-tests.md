---
title: Phase 3 end-to-end tests — federated query and result write
phase: 3
status: Pending
---

## Description

Write the end-to-end integration tests that prove Phase 3 is complete. The
canonical scenario from plan.md: register a MinIO connector → upload test data →
query via Trino → write result. A second scenario exercises DuckDB within a worker.

These tests run against the full local Docker Compose stack and are marked
`pytest.mark.e2e`. They are not run in unit-test CI; they require
`docker compose up` to be running.

## Acceptance criteria

### Scenario A — federated query via Trino

- [ ] Test uploads a small Parquet file (10 rows) to MinIO bucket `feanor-test`
      at key `test-data/sample.parquet` using `boto3` (or the MinIO Python SDK).

- [ ] Test registers a MinIO connector via `POST /v1/connectors`:
      ```json
      {
        "name": "test-minio",
        "type": "s3",
        "config": {
          "endpoint": "http://minio:9000",
          "access_key": "...",
          "secret_key": "..."
        }
      }
      ```

- [ ] Test verifies the Trino catalog file was created at
      `infra/trino/catalog/test-minio.properties`.

- [ ] Test calls `client.query("SELECT * FROM \"test-minio\".default.sample")` and
      asserts:
      - Returns exactly 10 rows.
      - Column names match the Parquet schema.
      - No data was copied to Postgres (asserted by checking datasets table).

- [ ] Test deletes the connector and asserts the catalog file is removed.

### Scenario B — DuckDB worker result write

- [ ] A minimal execution worker script (`tests/e2e/fixtures/worker_duckdb.py`)
      that:
      1. Reads `FEANOR_INPUTS` from env (JSON with `source_path` key).
      2. Opens a `DuckDBSession`.
      3. Queries the Parquet file at `source_path`.
      4. Writes the result to `FEANOR_RESULT_REF` using `write_result(...)`.
      5. Calls `PATCH /v1/executions/{FEANOR_EXECUTION_ID}/status` → `succeeded`.

- [ ] Integration test submits this worker as a `container_job_standard` execution
      with `inputs={"source_path": "s3://feanor-test/test-data/sample.parquet"}`.

- [ ] Test polls `GET /v1/executions/{id}` until status is `succeeded` (or
      timeout 120s).

- [ ] Test downloads the `result_ref` Parquet from MinIO and asserts it has 10 rows.

### Scenario C — log streaming

- [ ] Test submits an execution, waits for it to reach `running`, then calls
      `GET /v1/executions/{id}/logs?follow=true`.

- [ ] Asserts the response is `text/plain` streaming and contains at least one line.

- [ ] Asserts `log_ref` is set to an `s3://feanor-logs/...` path after completion.

### Test infrastructure

- [ ] `tests/e2e/conftest.py`:
      - `e2e_client` fixture: an authenticated `Client` pointed at
        `http://localhost:8000`, using a test `analyst` user credentials.
      - `minio_client` fixture: a `boto3` S3 client pointed at
        `http://localhost:9000`.
      - `setup_test_bucket` fixture: creates `feanor-test` bucket, uploads the
        sample Parquet, tears down after the session.

- [ ] `tests/e2e/sample_data.parquet` — a 10-row test fixture generated once and
      committed to the repo (use `pandas` + `pyarrow` to generate in a helper
      script, not at test runtime).

- [ ] `pytest.ini` (or `pyproject.toml`) includes marker `e2e`:
      `e2e: marks tests as end-to-end, requiring the full Docker stack`.

- [ ] Running `pytest -m e2e` with the stack up passes all three scenarios.

- [ ] Running `pytest -m "not e2e"` (unit + integration) does not attempt to
      connect to Trino or MinIO.

## Dependencies

- task-028 (Trino in Docker Compose)
- task-029 (connector → Trino catalog wiring)
- task-030 (SDK `client.query`)
- task-031 (CLI query command — smoke test it here too)
- task-032 (log streaming to MinIO)
- task-033 (DuckDB worker utility)

## Notes

- The sample Parquet fixture should be simple: columns `id` (int), `name` (str),
  `value` (float). 10 rows is enough to verify correctness without slowing tests.
- Scenario B requires the worker script to be packaged into a Docker image for
  the test. Use a `Dockerfile.test-worker` in `tests/e2e/fixtures/` that installs
  the `feanor[worker]` package and copies the script. Build it as part of the
  `docker compose up` step or build it explicitly in the test setup using
  `subprocess.run(["docker", "build", ...])`.
- End-to-end tests are intentionally slow. Do not add them to the unit-test CI
  job. A separate CI job (`e2e`) that runs `docker compose up --wait` then
  `pytest -m e2e` is the right model (that CI job is out of scope for this task).
- Trino may take 30–60 seconds to recognise a new catalog after the file is
  written. Add a retry loop (10 attempts, 10s apart) before asserting the query
  result in Scenario A.
