---
title: Example DAG — scheduled workflow submission via feanor SDK
phase: 4
status: Pending
---

## Description

Write the first real Airflow DAG: a scheduled pipeline that submits a Fëanor
workflow execution via the `feanor` SDK and waits for it to complete. This DAG
is the canonical example for data engineers and serves as the acceptance-test
vehicle for the Phase 4 "done when" criterion in plan.md.

The DAG is parametrized so it can target any workflow slug and input set via
Airflow Variables, making it reusable beyond the example.

## Acceptance criteria

### DAG file

- [ ] `dags/feanor_workflow_run.py` created with the following structure:

```python
from airflow.decorators import dag, task
from airflow.models import Variable
from pendulum import datetime
from hooks.feanor_hook import FeanorHook

@dag(
    dag_id="feanor_workflow_run",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["feanor", "example"],
    doc_md="""
    Submits a Fëanor workflow execution on a daily schedule.
    Configure via Airflow Variables:
    - `feanor_workflow_run__workflow_slug` (required)
    - `feanor_workflow_run__inputs` (optional JSON object, default: {})
    """,
)
def feanor_workflow_run():

    @task()
    def submit_workflow() -> str:
        slug = Variable.get("feanor_workflow_run__workflow_slug")
        inputs = Variable.get(
            "feanor_workflow_run__inputs",
            default_var="{}",
            deserialize_json=True,
        )
        client = FeanorHook().get_client()
        execution = client.executions.submit(
            workflow=slug,
            inputs=inputs,
            wait=True,
        )
        return str(execution.id)

    @task()
    def log_result(execution_id: str) -> None:
        client = FeanorHook().get_client()
        execution = client.executions.get(execution_id)
        print(f"Execution {execution_id} finished: status={execution.status}")
        print(f"  result_ref={execution.result_ref}")
        print(f"  log_ref={execution.log_ref}")
        if execution.status != "succeeded":
            raise ValueError(
                f"Workflow {execution.status}: expected succeeded"
            )

    log_result(submit_workflow())

feanor_workflow_run()
```

- [ ] The DAG is importable without errors:
      ```bash
      docker exec feanor-airflow-scheduler-1 airflow dags list
      ```
      Shows `feanor_workflow_run` with no import errors.

- [ ] The DAG appears in the Airflow web UI at `http://localhost:8081`.

### Airflow Variables

- [ ] A `airflow/seed_variables.py` script that populates example variables:
      ```python
      from airflow.models import Variable
      Variable.set("feanor_workflow_run__workflow_slug", "example-workflow:v1")
      Variable.set("feanor_workflow_run__inputs", "{}", serialize_json=False)
      ```

- [ ] The `airflow-init` service in `docker-compose.yml` updated to run
      `seed_variables.py` after the connection setup from task-038.

### Manual trigger test

- [ ] Documented manual test procedure (not automated):
      1. In the Airflow UI, trigger `feanor_workflow_run` manually.
      2. Confirm `submit_workflow` task completes (it will call the control plane;
         the workflow must exist — use one created in Phase 1/2 testing or create
         a fixture workflow via the API).
      3. Confirm `log_result` task prints execution details and status.
      4. Confirm the execution record is visible via
         `feanor executions list` in the CLI.

### Error handling

- [ ] If `feanor_workflow_run__workflow_slug` is not set, `submit_workflow`
      raises `airflow.exceptions.AirflowNotFoundException` with a clear message
      (Airflow `Variable.get` raises `KeyError` by default — catch and re-raise).

- [ ] If `execution.status == "failed"`, `log_result` raises `ValueError`, which
      marks the Airflow task as failed and triggers any configured alerts.

## Dependencies

- task-038 (FeanorHook — used directly in the DAG)
- task-025 (SDK `executions.submit(wait=True)` with long-polling)
- task-020 (workflow run endpoint — must be working for the submission to land)

## Notes

- Use the `@dag` / `@task` decorator API (Airflow 2.x TaskFlow). Do not use
  `PythonOperator` — TaskFlow is cleaner and avoids XCom boilerplate.
- `submit_workflow` returns the execution UUID as a string (XCom serialisation
  requires JSON-serialisable values). `log_result` receives it and re-fetches
  the execution record rather than serialising the whole object.
- `wait=True` in `client.executions.submit()` uses long-polling on the control
  plane side (task-024). The Airflow task will hold the worker process until the
  execution completes. Set `execution_timeout` on the DAG to a sensible ceiling
  (e.g. 1 hour) to prevent zombie tasks if the execution hangs.
- The `@daily` schedule with `catchup=False` means the DAG will not backfill
  missed runs. Suitable for example/demo use. Adjust schedule in production DAGs.
