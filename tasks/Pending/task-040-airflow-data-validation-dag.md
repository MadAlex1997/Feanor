---
title: Airflow DAG — data validation via Trino query and assertion
phase: 4
status: Pending
---

## Description

Write a data validation DAG that runs a Trino SQL query via the `feanor` SDK
(`client.query(sql)`), evaluates the result against configurable assertions, and
passes or fails the Airflow task accordingly. This is the standard pattern for
post-execution data quality checks and pipeline gate conditions.

## Acceptance criteria

### DAG file

- [ ] `dags/feanor_data_validation.py` created:

```python
from airflow.decorators import dag, task
from airflow.models import Variable
from pendulum import datetime
from hooks.feanor_hook import FeanorHook

@dag(
    dag_id="feanor_data_validation",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["feanor", "data-quality"],
    doc_md="""
    Runs a Trino SQL query and asserts on the result.
    Configure via Airflow Variables:
    - `feanor_data_validation__sql`          (required, Trino SQL)
    - `feanor_data_validation__min_rows`     (optional int, default: 1)
    - `feanor_data_validation__max_rows`     (optional int, default: None = no limit)
    - `feanor_data_validation__assert_expr`  (optional Python expression evaluated
                                              with `rows` in scope, e.g.
                                              "all(r['value'] > 0 for r in rows)")
    """,
)
def feanor_data_validation():

    @task()
    def run_query() -> list[dict]:
        sql = Variable.get("feanor_data_validation__sql")
        client = FeanorHook().get_client()
        rows = client.query(sql)
        return rows   # list of dicts, JSON-serialisable for XCom

    @task()
    def assert_result(rows: list[dict]) -> None:
        min_rows = int(Variable.get("feanor_data_validation__min_rows", default_var="1"))
        max_rows_raw = Variable.get("feanor_data_validation__max_rows", default_var="")
        assert_expr = Variable.get("feanor_data_validation__assert_expr", default_var="")

        if len(rows) < min_rows:
            raise AssertionError(
                f"Validation failed: expected at least {min_rows} rows, got {len(rows)}"
            )
        if max_rows_raw and len(rows) > int(max_rows_raw):
            raise AssertionError(
                f"Validation failed: expected at most {max_rows_raw} rows, got {len(rows)}"
            )
        if assert_expr:
            result = eval(assert_expr, {"rows": rows})  # noqa: S307
            if not result:
                raise AssertionError(
                    f"Validation failed: expression {assert_expr!r} evaluated to False"
                )
        print(f"Validation passed: {len(rows)} rows")

    assert_result(run_query())

feanor_data_validation()
```

- [ ] The DAG imports without errors:
      ```bash
      docker exec feanor-airflow-scheduler-1 airflow dags list
      ```
      Shows `feanor_data_validation` with no import errors.

### Security note on `eval`

- [ ] The `assert_expr` feature uses `eval` with a restricted globals dict.
      Add a comment marking the intentional use (`# noqa: S307`) and document
      in the DAG docstring that this variable must only be set by trusted users
      (platform admins or engineers with Airflow Variable write access).
      The Airflow RBAC model controls who can set Variables.

### Airflow Variables — seed values

- [ ] `airflow/seed_variables.py` (from task-039) extended with example values:
      ```python
      Variable.set(
          "feanor_data_validation__sql",
          "SELECT count(*) AS cnt FROM postgresql.public.datasets",
      )
      Variable.set("feanor_data_validation__min_rows", "1")
      ```
      This validates that the `datasets` table in Postgres (via Trino) has at
      least one row — a sensible smoke test after Phase 1 data is loaded.

### Manual trigger test

- [ ] Documented manual test procedure:
      1. Ensure Trino is running and the `postgresql` catalog is accessible
         (from task-028).
      2. Trigger `feanor_data_validation` manually in the Airflow UI.
      3. Confirm `run_query` returns rows from the Trino query.
      4. Confirm `assert_result` passes (or explicitly fails with a clear message
         if the assertion is not met).

### Reusability as a sensor / gate

- [ ] Add a brief `## Usage as a pipeline gate` section to the DAG's `doc_md`
      explaining how an engineer can add `ExternalTaskSensor` on `feanor_data_validation`
      from another DAG to block downstream work until data quality passes.

## Dependencies

- task-030 (SDK `client.query(sql)` via Trino — required for `run_query` task)
- task-038 (FeanorHook — used for authentication)
- task-028 (Trino in Docker Compose — required for Trino queries to resolve)
- task-039 (seed_variables.py script — extended here)

## Notes

- `client.query(sql)` returns a list of dicts (one per row). This is
  JSON-serialisable and safe to pass via Airflow XCom for small result sets.
  For large result sets (> ~10k rows), the validation query should aggregate
  in SQL (e.g. `SELECT count(*)`) rather than returning all rows.
- The `eval` approach for `assert_expr` is deliberately simple for MVP. For
  Phase 6 hardening, consider replacing it with a set of named assertion
  templates (e.g. `{"type": "row_count", "min": 1}`) to eliminate the eval.
  Add a TODO comment in the DAG to that effect.
- If `client.query()` raises a `TrinoQueryError`, the `run_query` task will
  fail and Airflow will mark it as failed — no additional error handling needed
  in the DAG. The SDK surfaces the error message from Trino.
- Schedule: `@daily` with `catchup=False` for the example. In practice,
  validation DAGs often run after an upstream pipeline DAG completes, using
  `TriggerDagRunOperator` or `ExternalTaskSensor`. Do not implement that
  wiring here — document it in the `doc_md` instead.
