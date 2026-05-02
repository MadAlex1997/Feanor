"""DAG: submit a Fëanor workflow execution on a schedule.

Configure via Airflow Variables:
  feanor_workflow_run__workflow_slug  (required) — e.g. "my-etl:v1"
  feanor_workflow_run__inputs         (optional JSON object, default: {})
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from airflow.decorators import dag, task
from airflow.exceptions import AirflowNotFoundException
from airflow.models import Variable
from pendulum import datetime


@dag(
    dag_id="feanor_workflow_run",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["feanor", "example"],
    dagrun_timeout=timedelta(hours=1),
    doc_md="""
## feanor_workflow_run

Submits a Fëanor workflow execution on a daily schedule and waits for completion.

### Variables

| Variable | Required | Description |
|---|---|---|
| `feanor_workflow_run__workflow_slug` | yes | Workflow slug, e.g. `my-etl:v1` |
| `feanor_workflow_run__inputs` | no | JSON object of workflow inputs (default: `{}`) |

### Usage as a template

Copy this DAG and rename it to target a different workflow or schedule.
Use `TriggerDagRunOperator` from another DAG to chain pipelines.
""",
)
def feanor_workflow_run() -> None:

    @task()
    def submit_workflow() -> str:
        try:
            slug = Variable.get("feanor_workflow_run__workflow_slug")
        except KeyError:
            raise AirflowNotFoundException(
                "Airflow Variable 'feanor_workflow_run__workflow_slug' is not set. "
                "Set it via Admin → Variables in the Airflow UI."
            )

        inputs: dict = Variable.get(
            "feanor_workflow_run__inputs",
            default_var="{}",
            deserialize_json=True,
        )

        from hooks.feanor_hook import FeanorHook
        from feanor.async_client import AsyncClient

        FeanorHook().inject_env()

        async def _run() -> str:
            async with AsyncClient() as client:
                execution = await client.executions.submit(
                    workflow=slug,
                    inputs=inputs,
                    wait=True,
                )
                return str(execution.id)

        return asyncio.run(_run())

    @task()
    def log_result(execution_id: str) -> None:
        from hooks.feanor_hook import FeanorHook
        from feanor.async_client import AsyncClient

        FeanorHook().inject_env()

        async def _run() -> None:
            async with AsyncClient() as client:
                execution = await client.executions.get(execution_id)
            print(f"Execution {execution_id} finished:")
            print(f"  status={execution.status}")
            print(f"  result_ref={execution.result_ref}")
            print(f"  log_ref={execution.log_ref}")

            if execution.status != "succeeded":
                raise ValueError(
                    f"Workflow execution {execution_id} ended with status "
                    f"'{execution.status}' — expected 'succeeded'."
                )

        asyncio.run(_run())

    log_result(submit_workflow())


feanor_workflow_run()
