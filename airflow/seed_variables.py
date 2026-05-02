"""Seed example Airflow Variables for Fëanor DAGs.

Run once by airflow-init on every fresh stack startup. Idempotent — only sets
variables that do not already exist so user-configured values are not overwritten.
"""
from __future__ import annotations

from airflow.models import Variable
from airflow.utils import db as airflow_db

_DEFAULTS: dict[str, str] = {
    # feanor_workflow_run DAG — point at an example workflow slug.
    # Override in the Airflow UI with a real workflow slug before triggering.
    "feanor_workflow_run__workflow_slug": "example-workflow:v1",
    "feanor_workflow_run__inputs": "{}",
    # feanor_data_validation DAG — validates that the datasets table has rows.
    "feanor_data_validation__sql": (
        "SELECT count(*) AS cnt FROM postgresql.public.datasets"
    ),
    "feanor_data_validation__min_rows": "0",
}

with airflow_db.create_session() as session:
    for key, value in _DEFAULTS.items():
        existing = session.query(Variable).filter_by(key=key).first()
        if existing is None:
            session.add(Variable(key=key, val=value))
            print(f"Created variable: {key}")
        else:
            print(f"Variable already exists, skipping: {key}")
    session.commit()
