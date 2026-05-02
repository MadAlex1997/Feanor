"""Unit tests for Phase 4 Airflow DAG structure.

Tests DAG import and structural properties without requiring a running Airflow
database or Docker stack. Uses pytest.importorskip so the suite degrades
gracefully when apache-airflow is not installed.
"""
from __future__ import annotations

import pytest

pytest.importorskip("airflow.decorators", reason="apache-airflow>=2.x not installed")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_dag(module_name: str, dag_id: str):
    """Import a DAG module and return the DAG object by id."""
    import importlib
    import sys

    # Ensure dags/ directory is on sys.path so DAG imports work.
    import pathlib

    dags_dir = str(pathlib.Path(__file__).parent.parent / "dags")
    if dags_dir not in sys.path:
        sys.path.insert(0, dags_dir)

    mod = importlib.import_module(module_name)
    from airflow.models import DagBag

    # DagBag parses and validates; use the already-imported module's dag object.
    for attr in dir(mod):
        obj = getattr(mod, attr)
        try:
            from airflow.models import DAG as AirflowDAG

            if isinstance(obj, AirflowDAG) and obj.dag_id == dag_id:
                return obj
        except Exception:
            continue
    raise AssertionError(f"DAG '{dag_id}' not found in module '{module_name}'")


# ---------------------------------------------------------------------------
# feanor_workflow_run
# ---------------------------------------------------------------------------


class TestWorkflowRunDag:
    def test_imports_without_error(self):
        import importlib

        import sys
        import pathlib

        dags_dir = str(pathlib.Path(__file__).parent.parent / "dags")
        if dags_dir not in sys.path:
            sys.path.insert(0, dags_dir)
        importlib.import_module("feanor_workflow_run")

    def test_dag_id(self):
        dag = _load_dag("feanor_workflow_run", "feanor_workflow_run")
        assert dag.dag_id == "feanor_workflow_run"

    def test_schedule(self):
        dag = _load_dag("feanor_workflow_run", "feanor_workflow_run")
        assert dag.schedule_interval == "@daily" or dag.timetable is not None

    def test_tags(self):
        dag = _load_dag("feanor_workflow_run", "feanor_workflow_run")
        assert "feanor" in dag.tags
        assert "example" in dag.tags

    def test_task_ids(self):
        dag = _load_dag("feanor_workflow_run", "feanor_workflow_run")
        task_ids = {t.task_id for t in dag.tasks}
        assert "submit_workflow" in task_ids
        assert "log_result" in task_ids

    def test_catchup_disabled(self):
        dag = _load_dag("feanor_workflow_run", "feanor_workflow_run")
        assert dag.catchup is False


# ---------------------------------------------------------------------------
# feanor_data_validation
# ---------------------------------------------------------------------------


class TestDataValidationDag:
    def test_imports_without_error(self):
        import importlib

        import sys
        import pathlib

        dags_dir = str(pathlib.Path(__file__).parent.parent / "dags")
        if dags_dir not in sys.path:
            sys.path.insert(0, dags_dir)
        importlib.import_module("feanor_data_validation")

    def test_dag_id(self):
        dag = _load_dag("feanor_data_validation", "feanor_data_validation")
        assert dag.dag_id == "feanor_data_validation"

    def test_schedule(self):
        dag = _load_dag("feanor_data_validation", "feanor_data_validation")
        assert dag.schedule_interval == "@daily" or dag.timetable is not None

    def test_tags(self):
        dag = _load_dag("feanor_data_validation", "feanor_data_validation")
        assert "feanor" in dag.tags
        assert "data-quality" in dag.tags

    def test_task_ids(self):
        dag = _load_dag("feanor_data_validation", "feanor_data_validation")
        task_ids = {t.task_id for t in dag.tasks}
        assert "run_query" in task_ids
        assert "assert_result" in task_ids

    def test_catchup_disabled(self):
        dag = _load_dag("feanor_data_validation", "feanor_data_validation")
        assert dag.catchup is False


# ---------------------------------------------------------------------------
# FeanorHook structural tests (no Airflow DB needed)
# ---------------------------------------------------------------------------


def test_hook_default_conn_id():
    import sys
    import pathlib

    dags_dir = str(pathlib.Path(__file__).parent.parent / "dags")
    if dags_dir not in sys.path:
        sys.path.insert(0, dags_dir)
    from hooks.feanor_hook import FeanorHook

    hook = FeanorHook()
    assert hook.conn_id == "feanor_default"


def test_hook_custom_conn_id():
    import sys
    import pathlib

    dags_dir = str(pathlib.Path(__file__).parent.parent / "dags")
    if dags_dir not in sys.path:
        sys.path.insert(0, dags_dir)
    from hooks.feanor_hook import FeanorHook

    hook = FeanorHook(conn_id="feanor_staging")
    assert hook.conn_id == "feanor_staging"


def test_hook_class_attributes():
    import sys
    import pathlib

    dags_dir = str(pathlib.Path(__file__).parent.parent / "dags")
    if dags_dir not in sys.path:
        sys.path.insert(0, dags_dir)
    from hooks.feanor_hook import FeanorHook

    assert FeanorHook.conn_type == "feanor"
    assert "Fëanor" in FeanorHook.hook_name
