"""DAG: run a Trino SQL query and assert on the result.

Useful as a data quality gate after pipeline runs. Configure via Airflow Variables:
  feanor_data_validation__sql          (required) — Trino SQL to run
  feanor_data_validation__min_rows     (optional int, default: 1)
  feanor_data_validation__max_rows     (optional int, default: no limit)
  feanor_data_validation__assert_expr  (optional Python expression with `rows` in scope)

Security note: assert_expr is evaluated with eval(). Only platform admins and
engineers with Airflow Variable write access should set this field.
"""
from __future__ import annotations

import asyncio

from airflow.decorators import dag, task
from airflow.exceptions import AirflowNotFoundException
from airflow.models import Variable
from pendulum import datetime


@dag(
    dag_id="feanor_data_validation",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["feanor", "data-quality"],
    doc_md="""
## feanor_data_validation

Runs a Trino SQL query via the Fëanor SDK and asserts on the result set.
Fails the task (and optionally alerts) when the assertion is not met.

### Variables

| Variable | Required | Description |
|---|---|---|
| `feanor_data_validation__sql` | yes | Trino SQL (e.g. `SELECT count(*) AS cnt FROM postgresql.public.orders`) |
| `feanor_data_validation__min_rows` | no | Minimum expected row count (default: 1) |
| `feanor_data_validation__max_rows` | no | Maximum expected row count (default: no limit) |
| `feanor_data_validation__assert_expr` | no | Python expression with `rows` in scope. **Trusted users only.** |

### Usage as a pipeline gate

Add an `ExternalTaskSensor` in a downstream DAG targeting this DAG's
`assert_result` task to block until data quality is confirmed.
""",
)
def feanor_data_validation() -> None:

    @task()
    def run_query() -> list[dict]:
        try:
            sql = Variable.get("feanor_data_validation__sql")
        except KeyError:
            raise AirflowNotFoundException(
                "Airflow Variable 'feanor_data_validation__sql' is not set. "
                "Set it via Admin → Variables in the Airflow UI."
            )

        from hooks.feanor_hook import FeanorHook
        from feanor.async_client import AsyncClient

        FeanorHook().inject_env()

        async def _run() -> list[dict]:
            async with AsyncClient() as client:
                result = await client.query(sql)
                return result.rows  # already list[dict]

        rows = asyncio.run(_run())
        print(f"Query returned {len(rows)} row(s).")
        return rows

    @task()
    def assert_result(rows: list[dict]) -> None:
        min_rows = int(Variable.get("feanor_data_validation__min_rows", default_var="1"))
        max_rows_raw = Variable.get("feanor_data_validation__max_rows", default_var="")
        assert_expr = Variable.get("feanor_data_validation__assert_expr", default_var="")

        if len(rows) < min_rows:
            raise AssertionError(
                f"Validation failed: expected at least {min_rows} row(s), got {len(rows)}."
            )

        if max_rows_raw:
            max_rows = int(max_rows_raw)
            if len(rows) > max_rows:
                raise AssertionError(
                    f"Validation failed: expected at most {max_rows} row(s), got {len(rows)}."
                )

        if assert_expr:
            # noqa: S307 — eval is intentional; access is gated by Airflow RBAC on Variables.
            passed = eval(assert_expr, {"rows": rows, "__builtins__": {}})  # noqa: S307
            if not passed:
                raise AssertionError(
                    f"Validation failed: expression {assert_expr!r} evaluated to False. "
                    f"First row: {rows[0] if rows else '(no rows)'}"
                )

        print(f"Validation passed: {len(rows)} row(s), all assertions met.")

    assert_result(run_query())


feanor_data_validation()
