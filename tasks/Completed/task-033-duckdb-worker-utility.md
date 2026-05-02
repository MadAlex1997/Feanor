---
title: DuckDB wrapper utility for execution workers
phase: 3
status: Pending
---

## Description

Provide a lightweight DuckDB utility module (`feanor.worker.duckdb`) that
execution workers can import to run in-process analytical queries against local
files, Parquet/CSV objects in MinIO, or data fetched during the job. DuckDB is
always embedded — it is never a server — and this module is only intended for
use inside execution containers.

## Acceptance criteria

- [ ] `feanor/worker/__init__.py` — new subpackage marker.

- [ ] `feanor/worker/duckdb.py` — exports a `DuckDBSession` context manager:

      ```python
      from feanor.worker.duckdb import DuckDBSession

      with DuckDBSession() as db:
          df = db.query("SELECT * FROM read_parquet('s3://bucket/file.parquet')")
          db.execute("COPY (SELECT ...) TO 's3://bucket/out.parquet' (FORMAT PARQUET)")
      ```

- [ ] `DuckDBSession.__init__` parameters:
      - `s3_endpoint: str | None = None` — MinIO/S3 endpoint URL. Reads from
        `FEANOR_S3_ENDPOINT` env var if not provided.
      - `s3_access_key: str | None = None` — reads `AWS_ACCESS_KEY_ID` env var.
      - `s3_secret_key: str | None = None` — reads `AWS_SECRET_ACCESS_KEY` env var.
      - `read_only: bool = False`
      - `memory_limit: str = "1GB"` — DuckDB memory limit string.

- [ ] On `__enter__`, `DuckDBSession`:
      1. Opens an in-memory DuckDB connection.
      2. Calls `INSTALL httpfs; LOAD httpfs;` to enable S3 access.
      3. Configures S3 settings via DuckDB `SET` commands if S3 credentials are
         present (`s3_endpoint`, `s3_region='us-east-1'`, `s3_url_style='path'`,
         `s3_use_ssl=false` for MinIO).
      4. Sets `memory_limit`.
      5. Returns `self`.

- [ ] `DuckDBSession.query(sql: str) -> list[dict]`:
      - Executes `sql` and returns all rows as a list of dicts.

- [ ] `DuckDBSession.query_df(sql: str) -> "pandas.DataFrame"`:
      - Returns a pandas DataFrame. Raises `ImportError` with a helpful message
        if pandas is not installed in the worker environment.

- [ ] `DuckDBSession.execute(sql: str) -> None`:
      - Executes `sql` with no return value. Use for `COPY`, `CREATE TABLE`, etc.

- [ ] `DuckDBSession.__exit__` closes the connection (even on exception).

- [ ] `duckdb>=0.10` added to `[feature.worker.dependencies]` in `pixi.toml`
      (a new `[feature.worker]` section, separate from `api`).

- [ ] `feanor/worker/result.py` — `write_result(data: list[dict] | pd.DataFrame,
      result_ref: str) -> None`:
      - Writes the result to the path given by `result_ref` (S3/MinIO Parquet).
      - Used by workers to fulfil the execution worker contract (step 4 in plan.md).
      - Uses DuckDB's `COPY ... TO ... (FORMAT PARQUET)` internally.

- [ ] Unit tests:
      - `DuckDBSession.query("SELECT 42 AS n")` returns `[{"n": 42}]`.
      - S3 settings are applied when credentials are provided (mock DuckDB's
        `SET` calls).
      - `__exit__` closes the connection even if `query` raises.
      - `write_result` calls the correct DuckDB `COPY` statement.

## Dependencies

- task-022 (worker base image — the utility lives in the same `feanor` package
  that is installed in worker containers)
- task-028 (MinIO running so integration tests can exercise S3 reads)

## Notes

- `duckdb` must be in a separate `[feature.worker]` pixi feature so that the
  API service (`[feature.api]`) does not pull in DuckDB. Worker containers
  install the `worker` feature; the API installs `api`.
- DuckDB's S3 support requires `INSTALL httpfs; LOAD httpfs;` once per
  connection. This is idempotent and fast.
- `s3_url_style='path'` is required for MinIO. AWS S3 uses virtual-hosted style
  (`s3_url_style='vhost'`). The session should default to `path` when
  `s3_endpoint` is set (MinIO) and `vhost` when it is not (AWS).
- The `write_result` helper writes Parquet by default because DuckDB can write
  Parquet natively without pandas. JSON and CSV can be added later if needed.
- Do not include heavy ML dependencies (torch, sklearn) in the worker package.
  Workers that need them build their own image on top of the base worker image.
